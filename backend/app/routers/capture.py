from __future__ import annotations

import csv
import io
import json
import sys
from datetime import date, time
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import get_settings
from app.core.database import get_db_conn
from app.core.security import get_current_user
from app.services.rules_engine import evaluate_rules
from app.services.s3_service import upload_bytes_to_s3
from etl.psqi_calculator import compute_ess, compute_objective_kpis, compute_psqi
from etl.run_etl import run_etl
from etl.validators import REQUIRED_CSV_COLUMNS, validate_csv_records, validate_sleep_night_row

router = APIRouter(prefix="/api/capture", tags=["capture"])


class QuestionnairePayload(BaseModel):
    participante_codigo: Optional[str] = None
    consentimiento_aceptado: bool = True
    edad: Optional[int] = Field(default=None, ge=16, le=65)
    sexo: Optional[str] = None
    facultad: Optional[str] = None
    carrera: Optional[str] = None
    ciclo: Optional[int] = Field(default=None, ge=1, le=12)
    fecha: date
    # Habitos
    pantallas_antes_dormir: str
    cafeina_nivel: str
    ejercicio_nivel: str
    estres_nivel: str
    regularidad_horarios: str
    # PSQI
    hora_acostarse: str
    minutos_latencia: int = Field(ge=0, le=360)
    hora_levantarse: str
    horas_sueno_real: float = Field(gt=0, le=24)
    psqi_items: Dict[str, int]
    # ESS (8 situaciones)
    ess_items: List[int] = Field(min_length=8, max_length=8)


class SleepNightPayload(BaseModel):
    participante_codigo: Optional[str] = None
    fecha: date
    tib_min: float = Field(gt=0, le=1440)
    tst_min: float = Field(gt=0, le=1440)
    sol_min: float = Field(ge=0, le=360)
    despertares: int = Field(ge=0, le=50)
    min_n1: float = Field(ge=0)
    min_n2: float = Field(ge=0)
    min_n3: float = Field(ge=0)
    min_rem: float = Field(ge=0)


def _resolve_participante(cur, user, codigo: Optional[str]) -> Dict:
    target_code = codigo or user.get("participante_codigo")
    if target_code:
        cur.execute("SELECT * FROM glympho_oltp.participante WHERE codigo = %s", (target_code,))
        row = cur.fetchone()
        if row:
            return row
    if user["rol"] in ("investigador", "admin"):
        raise HTTPException(status_code=400, detail="Debe especificar un codigo de participante valido (ej. UNT-001).")
    raise HTTPException(status_code=404, detail="Participante no encontrado para este usuario.")


@router.post("/questionnaire")
def submit_questionnaire(body: QuestionnairePayload, user=Depends(get_current_user)):
    if not body.consentimiento_aceptado:
        raise HTTPException(status_code=400, detail="El consentimiento informado es obligatorio.")

    # Validar calculos antes de persistir
    try:
        psqi_calc = compute_psqi(
            body.hora_acostarse,
            body.minutos_latencia,
            body.hora_levantarse,
            body.horas_sueno_real,
            body.psqi_items,
        )
        ess_calc = compute_ess(body.ess_items)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    settings = get_settings()
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            # Permitir crear nuevo participante anonimizado si investigador/admin registra uno nuevo
            target_code = body.participante_codigo or user.get("participante_codigo")
            part = None
            if target_code:
                cur.execute("SELECT * FROM glympho_oltp.participante WHERE codigo = %s", (target_code,))
                part = cur.fetchone()

            if not part and user["rol"] in ("investigador", "admin") and body.facultad and body.carrera:
                cur.execute("SELECT COALESCE(MAX(id), 0) + 1 AS nxt FROM glympho_oltp.participante")
                nxt = int(cur.fetchone()["nxt"])
                new_code = f"UNT-{nxt:03d}"
                cur.execute(
                    """
                    INSERT INTO glympho_oltp.participante (codigo, edad, sexo, facultad, carrera, ciclo)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (new_code, body.edad or 21, body.sexo or "F", body.facultad, body.carrera, body.ciclo or 5),
                )
                part = cur.fetchone()
                cur.execute(
                    "INSERT INTO glympho_oltp.consentimiento (participante_id, aceptado) VALUES (%s, TRUE)",
                    (part["id"],),
                )

            if not part:
                raise HTTPException(status_code=404, detail="Participante no encontrado.")

            pid = part["id"]
            if body.edad and body.facultad and body.carrera and body.ciclo:
                cur.execute(
                    """
                    UPDATE glympho_oltp.participante
                    SET edad = %s, sexo = COALESCE(%s, sexo), facultad = %s, carrera = %s, ciclo = %s
                    WHERE id = %s
                    """,
                    (body.edad, body.sexo, body.facultad, body.carrera, body.ciclo, pid),
                )

            cur.execute(
                """
                INSERT INTO glympho_oltp.habito_sueno
                    (participante_id, fecha, pantallas_antes_dormir, cafeina_nivel, ejercicio_nivel, estres_nivel, regularidad_horarios)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (participante_id, fecha) DO UPDATE SET
                    pantallas_antes_dormir = EXCLUDED.pantallas_antes_dormir,
                    cafeina_nivel = EXCLUDED.cafeina_nivel,
                    ejercicio_nivel = EXCLUDED.ejercicio_nivel,
                    estres_nivel = EXCLUDED.estres_nivel,
                    regularidad_horarios = EXCLUDED.regularidad_horarios
                """,
                (
                    pid,
                    body.fecha,
                    body.pantallas_antes_dormir,
                    body.cafeina_nivel,
                    body.ejercicio_nivel,
                    body.estres_nivel,
                    body.regularidad_horarios,
                ),
            )

            hp, mp = [int(x) for x in body.hora_acostarse.split(":")[:2]]
            hl, ml = [int(x) for x in body.hora_levantarse.split(":")[:2]]
            cur.execute(
                """
                INSERT INTO glympho_oltp.cuestionario_psqi
                    (participante_id, fecha, hora_acostarse, minutos_latencia, hora_levantarse, horas_sueno_real)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (participante_id, fecha) DO UPDATE SET
                    hora_acostarse = EXCLUDED.hora_acostarse,
                    minutos_latencia = EXCLUDED.minutos_latencia,
                    hora_levantarse = EXCLUDED.hora_levantarse,
                    horas_sueno_real = EXCLUDED.horas_sueno_real
                RETURNING id
                """,
                (pid, body.fecha, time(hp, mp), body.minutos_latencia, time(hl, ml), body.horas_sueno_real),
            )
            psqi_id = cur.fetchone()["id"]
            cur.execute("DELETE FROM glympho_oltp.respuesta_psqi WHERE psqi_id = %s", (psqi_id,))
            for ic, iv in body.psqi_items.items():
                cur.execute(
                    "INSERT INTO glympho_oltp.respuesta_psqi (psqi_id, item_codigo, valor) VALUES (%s, %s, %s)",
                    (psqi_id, ic, int(iv)),
                )

            cur.execute(
                """
                INSERT INTO glympho_oltp.cuestionario_ess (participante_id, fecha)
                VALUES (%s, %s)
                ON CONFLICT (participante_id, fecha) DO UPDATE SET fecha = EXCLUDED.fecha
                RETURNING id
                """,
                (pid, body.fecha),
            )
            ess_id = cur.fetchone()["id"]
            cur.execute("DELETE FROM glympho_oltp.respuesta_ess WHERE ess_id = %s", (ess_id,))
            for idx, val in enumerate(body.ess_items, start=1):
                cur.execute(
                    "INSERT INTO glympho_oltp.respuesta_ess (ess_id, situacion_num, valor) VALUES (%s, %s, %s)",
                    (ess_id, idx, int(val)),
                )

            cur.execute("SELECT * FROM glympho_oltp.recomendacion_regla WHERE activo = TRUE")
            rules = cur.fetchall()
        conn.commit()

    etl_res = run_etl(origen="captura_cuestionario", dsn=settings.pg_dsn, participante_id=pid)
    alerts = evaluate_rules(
        {"PSQI": psqi_calc["psqi_global"], "ESS": ess_calc["ess_total"]},
        rules,
    )
    return {
        "participante_codigo": part["codigo"],
        "fecha": str(body.fecha),
        "psqi": psqi_calc,
        "ess": ess_calc,
        "alerts": alerts,
        "etl": etl_res,
    }


@router.post("/sleep-night")
def submit_sleep_night(body: SleepNightPayload, user=Depends(get_current_user)):
    ok, clean, err = validate_sleep_night_row(body.model_dump(), row_index=1)
    if not ok or clean is None:
        raise HTTPException(status_code=400, detail=err)

    settings = get_settings()
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            part = _resolve_participante(cur, user, body.participante_codigo)
            cur.execute(
                """
                INSERT INTO glympho_oltp.registro_sueno_noche
                    (participante_id, fecha, tib_min, tst_min, sol_min, despertares,
                     min_n1, min_n2, min_n3, min_rem, origen)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'manual')
                ON CONFLICT (participante_id, fecha) DO UPDATE SET
                    tib_min = EXCLUDED.tib_min,
                    tst_min = EXCLUDED.tst_min,
                    sol_min = EXCLUDED.sol_min,
                    despertares = EXCLUDED.despertares,
                    min_n1 = EXCLUDED.min_n1,
                    min_n2 = EXCLUDED.min_n2,
                    min_n3 = EXCLUDED.min_n3,
                    min_rem = EXCLUDED.min_rem,
                    origen = 'manual'
                """,
                (
                    part["id"], clean["fecha"], clean["tib_min"], clean["tst_min"],
                    clean["sol_min"], clean["despertares"], clean["min_n1"],
                    clean["min_n2"], clean["min_n3"], clean["min_rem"],
                ),
            )
        conn.commit()

    etl_res = run_etl(origen="captura_noche_manual", dsn=settings.pg_dsn, participante_id=part["id"])
    kpis = compute_objective_kpis(clean["tib_min"], clean["tst_min"], clean["sol_min"], clean["min_n3"])
    return {"participante_codigo": part["codigo"], "fecha": str(clean["fecha"]), "kpis": kpis, "etl": etl_res}


@router.post("/sleep-csv")
async def upload_sleep_csv(
    file: UploadFile = File(...),
    participante_codigo: Optional[str] = Form(default=None),
    user=Depends(get_current_user),
):
    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="El archivo CSV esta vacio.")

    text = raw_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or any(col not in reader.fieldnames for col in REQUIRED_CSV_COLUMNS):
        raise HTTPException(
            status_code=400,
            detail=f"El CSV debe incluir las columnas: {', '.join(REQUIRED_CSV_COLUMNS)}",
        )

    rows = list(reader)
    valid_rows, errors = validate_csv_records(rows)
    settings = get_settings()
    s3_key = upload_bytes_to_s3(f"csv/{file.filename}", raw_bytes, "text/csv")

    with get_db_conn() as conn:
        with conn.cursor() as cur:
            part = _resolve_participante(cur, user, participante_codigo)
            estado = "procesado" if valid_rows and not errors else ("parcial" if valid_rows else "rechazado")

            cur.execute(
                """
                INSERT INTO glympho_oltp.carga_archivo
                    (participante_id, usuario_id, nombre_archivo, s3_key,
                     registros_totales, registros_validos, registros_rechazados, estado, detalle_errores)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                RETURNING id
                """,
                (
                    part["id"], user["id"], file.filename, s3_key,
                    len(rows), len(valid_rows), len(errors), estado, json.dumps(errors[:30]),
                ),
            )
            carga_id = cur.fetchone()["id"]

            affected_pids = set()
            for r in valid_rows:
                target_pid = part["id"]
                if r.get("codigo_participante"):
                    cur.execute("SELECT id FROM glympho_oltp.participante WHERE codigo = %s", (r["codigo_participante"],))
                    found = cur.fetchone()
                    if found:
                        target_pid = found["id"]
                affected_pids.add(target_pid)

                cur.execute(
                    """
                    INSERT INTO glympho_oltp.registro_sueno_noche
                        (participante_id, fecha, tib_min, tst_min, sol_min, despertares,
                         min_n1, min_n2, min_n3, min_rem, origen, carga_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'csv', %s)
                    ON CONFLICT (participante_id, fecha) DO UPDATE SET
                        tib_min = EXCLUDED.tib_min,
                        tst_min = EXCLUDED.tst_min,
                        sol_min = EXCLUDED.sol_min,
                        despertares = EXCLUDED.despertares,
                        min_n1 = EXCLUDED.min_n1,
                        min_n2 = EXCLUDED.min_n2,
                        min_n3 = EXCLUDED.min_n3,
                        min_rem = EXCLUDED.min_rem,
                        origen = 'csv',
                        carga_id = EXCLUDED.carga_id
                    """,
                    (
                        target_pid, r["fecha"], r["tib_min"], r["tst_min"], r["sol_min"],
                        r["despertares"], r["min_n1"], r["min_n2"], r["min_n3"], r["min_rem"], carga_id,
                    ),
                )
        conn.commit()

    single_pid = next(iter(affected_pids)) if len(affected_pids) == 1 else None
    etl_res = run_etl(origen="carga_csv", dsn=settings.pg_dsn, participante_id=single_pid) if valid_rows else None
    return {
        "carga_id": carga_id,
        "archivo": file.filename,
        "participante_codigo": part["codigo"],
        "estado": estado,
        "registros_totales": len(rows),
        "registros_validos": len(valid_rows),
        "registros_rechazados": len(errors),
        "errores": errors[:20],
        "etl": etl_res,
    }


@router.get("/csv-template")
def download_csv_template():
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(REQUIRED_CSV_COLUMNS)
    w.writerow(["2026-11-25", 480, 420, 18, 2, 25, 220, 88, 87])
    w.writerow(["2026-11-26", 495, 435, 16, 1, 24, 224, 94, 93])
    return Response(
        content=buf.getvalue().encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=plantilla_wearable_glymphocare.csv"},
    )
