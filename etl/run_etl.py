"""
Proceso ETL completo e idempotente de GlymphoCare (RETL-01 .. RETL-06).
Extrae desde glympho_oltp, valida/calcula PSQI (7 componentes), ESS y KPIs objetivos,
y carga el Data Mart en esquema estrella (glympho_dw) registrando logs auditables.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.rows import dict_row

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from etl.psqi_calculator import compute_ess, compute_objective_kpis, compute_psqi

DIAS_SEMANA = {
    1: "Lunes",
    2: "Martes",
    3: "Miercoles",
    4: "Jueves",
    5: "Viernes",
    6: "Sabado",
    7: "Domingo",
}

MESES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


def get_dsn() -> str:
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        env_path = ROOT_DIR / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8-sig").splitlines():
                if line.strip().startswith("DATABASE_URL="):
                    dsn = line.split("=", 1)[1].strip()
                    break
    if not dsn:
        dsn = "postgresql://glympho:glympho_secret_2026@localhost:5433/glymphocare"
    return dsn.replace("postgresql+psycopg://", "postgresql://")


def _rango_edad(edad: int) -> str:
    if edad <= 19:
        return "17-19"
    if edad <= 22:
        return "20-22"
    if edad <= 25:
        return "23-25"
    return "26+"


def _ciclo_academico(fecha: date) -> str:
    return f"{fecha.year}-I" if fecha.month <= 7 else f"{fecha.year}-II"


def _upsert_dim_tiempo(cur: psycopg.Cursor, fecha: date) -> int:
    iso_dow = fecha.isoweekday()
    iso_week = fecha.isocalendar().week
    cur.execute(
        """
        INSERT INTO glympho_dw.dim_tiempo
            (fecha, dia_semana_num, dia_semana, es_fin_semana, semana_anio, mes, mes_nombre, anio, ciclo_academico)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (fecha) DO UPDATE SET
            dia_semana_num = EXCLUDED.dia_semana_num,
            dia_semana = EXCLUDED.dia_semana,
            es_fin_semana = EXCLUDED.es_fin_semana
        RETURNING tiempo_key
        """,
        (
            fecha,
            iso_dow,
            DIAS_SEMANA[iso_dow],
            iso_dow >= 6,
            iso_week,
            fecha.month,
            MESES[fecha.month],
            fecha.year,
            _ciclo_academico(fecha),
        ),
    )
    return cur.fetchone()["tiempo_key"]


def _upsert_dim_carrera(cur: psycopg.Cursor, carrera: str, facultad: str) -> int:
    cur.execute(
        """
        INSERT INTO glympho_dw.dim_carrera (carrera, facultad)
        VALUES (%s, %s)
        ON CONFLICT (carrera) DO UPDATE SET facultad = EXCLUDED.facultad
        RETURNING carrera_key
        """,
        (carrera, facultad),
    )
    return cur.fetchone()["carrera_key"]


def _upsert_dim_participante(cur: psycopg.Cursor, part: Dict[str, Any]) -> int:
    cur.execute(
        """
        INSERT INTO glympho_dw.dim_participante
            (participante_id_oltp, codigo, edad, rango_edad, sexo, ciclo)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (participante_id_oltp) DO UPDATE SET
            edad = EXCLUDED.edad,
            rango_edad = EXCLUDED.rango_edad,
            sexo = EXCLUDED.sexo,
            ciclo = EXCLUDED.ciclo
        RETURNING participante_key
        """,
        (
            part["id"],
            part["codigo"],
            part["edad"],
            _rango_edad(int(part["edad"])),
            part["sexo"],
            part["ciclo"],
        ),
    )
    return cur.fetchone()["participante_key"]


def _upsert_dim_habito(cur: psycopg.Cursor, h: Dict[str, str]) -> int:
    cur.execute(
        """
        INSERT INTO glympho_dw.dim_habito
            (uso_pantallas, cafeina, ejercicio, estres, regularidad_horarios)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (uso_pantallas, cafeina, ejercicio, estres, regularidad_horarios)
        DO UPDATE SET uso_pantallas = EXCLUDED.uso_pantallas
        RETURNING habito_key
        """,
        (
            h["pantallas_antes_dormir"],
            h["cafeina_nivel"],
            h["ejercicio_nivel"],
            h["estres_nivel"],
            h["regularidad_horarios"],
        ),
    )
    return cur.fetchone()["habito_key"]


def run_etl(
    origen: str = "manual",
    dsn: Optional[str] = None,
    participante_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Ejecuta el pipeline OLTP -> Data Mart (completo o incremental por participante) con log auditable."""
    conn_dsn = (dsn or get_dsn()).replace("postgresql+psycopg://", "postgresql://")
    errors: List[str] = []
    filas_leidas = 0
    filas_cargadas = 0
    filas_rechazadas = 0
    log_id: Optional[int] = None

    with psycopg.connect(conn_dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO glympho_dw.etl_ejecucion_log (origen, estado)
                VALUES (%s, 'en_proceso')
                RETURNING id
                """,
                (origen,),
            )
            log_id = cur.fetchone()["id"]
            conn.commit()

        try:
            with conn.cursor() as cur:
                # Cache de fechas existentes en dim_tiempo para evitar round-trips repetidos
                cur.execute("SELECT tiempo_key, fecha FROM glympho_dw.dim_tiempo")
                tiempo_cache: Dict[date, int] = {r["fecha"]: r["tiempo_key"] for r in cur.fetchall()}

                def get_tiempo_key(f: date) -> int:
                    if f not in tiempo_cache:
                        tiempo_cache[f] = _upsert_dim_tiempo(cur, f)
                    return tiempo_cache[f]

                # 1. Dimensiones base de participantes y carreras
                if participante_id is not None:
                    cur.execute("SELECT * FROM glympho_oltp.participante WHERE id = %s", (participante_id,))
                else:
                    cur.execute("SELECT * FROM glympho_oltp.participante ORDER BY id")
                participantes = cur.fetchall()
                part_map: Dict[int, Dict[str, Any]] = {}
                carrera_cache: Dict[tuple[str, str], int] = {}
                for p in participantes:
                    pk = _upsert_dim_participante(cur, p)
                    c_pair = (p["carrera"], p["facultad"])
                    if c_pair not in carrera_cache:
                        carrera_cache[c_pair] = _upsert_dim_carrera(cur, p["carrera"], p["facultad"])
                    part_map[p["id"]] = {"participante_key": pk, "carrera_key": carrera_cache[c_pair], "codigo": p["codigo"]}

                # Cargar habitos ordenados por participante y fecha
                if participante_id is not None:
                    cur.execute(
                        "SELECT * FROM glympho_oltp.habito_sueno WHERE participante_id = %s ORDER BY fecha",
                        (participante_id,),
                    )
                else:
                    cur.execute("SELECT * FROM glympho_oltp.habito_sueno ORDER BY participante_id, fecha")
                habitos_por_part: Dict[int, List[Dict[str, Any]]] = {}
                hab_cache: Dict[tuple[str, str, str, str, str], int] = {}
                for h in cur.fetchall():
                    h_sig = (
                        h["pantallas_antes_dormir"],
                        h["cafeina_nivel"],
                        h["ejercicio_nivel"],
                        h["estres_nivel"],
                        h["regularidad_horarios"],
                    )
                    if h_sig not in hab_cache:
                        hab_cache[h_sig] = _upsert_dim_habito(cur, h)
                    h["habito_key"] = hab_cache[h_sig]
                    habitos_por_part.setdefault(h["participante_id"], []).append(h)

                default_habito_key = _upsert_dim_habito(
                    cur,
                    {
                        "pantallas_antes_dormir": "<=1h",
                        "cafeina_nivel": "antes_14h_o_ninguna",
                        "ejercicio_nivel": "<3_dias",
                        "estres_nivel": "medio",
                        "regularidad_horarios": "regular",
                    },
                )

                def resolve_habito_key(part_id: int, ref_date: date) -> int:
                    lista = habitos_por_part.get(part_id, [])
                    if not lista:
                        return default_habito_key
                    elegido = lista[0]
                    for item in lista:
                        if item["fecha"] <= ref_date:
                            elegido = item
                        else:
                            break
                    return elegido["habito_key"]

                # 2. Procesar cuestionarios (PSQI + ESS) -> fact_cuestionario (prefetch masivo)
                if participante_id is not None:
                    cur.execute(
                        "SELECT * FROM glympho_oltp.cuestionario_psqi WHERE participante_id = %s ORDER BY fecha",
                        (participante_id,),
                    )
                else:
                    cur.execute("SELECT * FROM glympho_oltp.cuestionario_psqi ORDER BY participante_id, fecha")
                psqi_rows = cur.fetchall()

                if participante_id is not None:
                    cur.execute(
                        "SELECT * FROM glympho_oltp.cuestionario_ess WHERE participante_id = %s",
                        (participante_id,),
                    )
                else:
                    cur.execute("SELECT * FROM glympho_oltp.cuestionario_ess")
                ess_rows = cur.fetchall()
                ess_by_key = {(r["participante_id"], r["fecha"]): r for r in ess_rows}
                ess_by_part: Dict[int, List[Dict[str, Any]]] = {}
                for er in ess_rows:
                    ess_by_part.setdefault(er["participante_id"], []).append(er)

                psqi_items_by_id: Dict[int, Dict[str, int]] = {}
                ess_items_by_id: Dict[int, Dict[int, int]] = {}
                if psqi_rows:
                    psqi_ids = [r["id"] for r in psqi_rows]
                    cur.execute(
                        "SELECT psqi_id, item_codigo, valor FROM glympho_oltp.respuesta_psqi WHERE psqi_id = ANY(%s)",
                        (psqi_ids,),
                    )
                    for r in cur.fetchall():
                        psqi_items_by_id.setdefault(r["psqi_id"], {})[r["item_codigo"]] = int(r["valor"])
                if ess_rows:
                    ess_ids = [r["id"] for r in ess_rows]
                    cur.execute(
                        "SELECT ess_id, situacion_num, valor FROM glympho_oltp.respuesta_ess WHERE ess_id = ANY(%s)",
                        (ess_ids,),
                    )
                    for r in cur.fetchall():
                        ess_items_by_id.setdefault(r["ess_id"], {})[int(r["situacion_num"])] = int(r["valor"])

                fact_cuest_batch: List[tuple] = []
                for q in psqi_rows:
                    filas_leidas += 1
                    pid = q["participante_id"]
                    if pid not in part_map:
                        filas_rechazadas += 1
                        errors.append(f"PSQI id={q['id']}: participante {pid} inexistente.")
                        continue

                    psqi_items = psqi_items_by_id.get(q["id"], {})
                    ess_hdr = ess_by_key.get((pid, q["fecha"]))
                    if not ess_hdr and ess_by_part.get(pid):
                        ess_hdr = min(ess_by_part[pid], key=lambda x: abs((x["fecha"] - q["fecha"]).days))

                    if not ess_hdr:
                        filas_rechazadas += 1
                        errors.append(f"PSQI id={q['id']} ({q['fecha']}): sin ESS asociado.")
                        continue

                    ess_items = ess_items_by_id.get(ess_hdr["id"], {})
                    try:
                        psqi_calc = compute_psqi(
                            q["hora_acostarse"],
                            int(q["minutos_latencia"]),
                            q["hora_levantarse"],
                            float(q["horas_sueno_real"]),
                            psqi_items,
                        )
                        ess_calc = compute_ess(ess_items)
                    except ValueError as exc:
                        filas_rechazadas += 1
                        errors.append(f"Cuestionario participante {pid} ({q['fecha']}): {exc}")
                        continue

                    tk = get_tiempo_key(q["fecha"])
                    hk = resolve_habito_key(pid, q["fecha"])
                    pm = part_map[pid]
                    fact_cuest_batch.append(
                        (
                            tk, pm["participante_key"], pm["carrera_key"], hk,
                            psqi_calc["c1_calidad"], psqi_calc["c2_latencia"], psqi_calc["c3_duracion"],
                            psqi_calc["c4_eficiencia"], psqi_calc["c5_alteraciones"],
                            psqi_calc["c6_medicacion"], psqi_calc["c7_disfuncion"],
                            psqi_calc["psqi_global"], ess_calc["ess_total"],
                            psqi_calc["clasificacion_psqi"], ess_calc["clasificacion_ess"],
                        )
                    )

                if fact_cuest_batch:
                    cur.executemany(
                        """
                        INSERT INTO glympho_dw.fact_cuestionario (
                            tiempo_key, participante_key, carrera_key, habito_key,
                            c1_calidad, c2_latencia, c3_duracion, c4_eficiencia,
                            c5_alteraciones, c6_medicacion, c7_disfuncion,
                            psqi_global, ess_total, clasificacion_psqi, clasificacion_ess, actualizado_en
                        )
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                        ON CONFLICT (participante_key, tiempo_key) DO UPDATE SET
                            carrera_key = EXCLUDED.carrera_key,
                            habito_key = EXCLUDED.habito_key,
                            c1_calidad = EXCLUDED.c1_calidad,
                            c2_latencia = EXCLUDED.c2_latencia,
                            c3_duracion = EXCLUDED.c3_duracion,
                            c4_eficiencia = EXCLUDED.c4_eficiencia,
                            c5_alteraciones = EXCLUDED.c5_alteraciones,
                            c6_medicacion = EXCLUDED.c6_medicacion,
                            c7_disfuncion = EXCLUDED.c7_disfuncion,
                            psqi_global = EXCLUDED.psqi_global,
                            ess_total = EXCLUDED.ess_total,
                            clasificacion_psqi = EXCLUDED.clasificacion_psqi,
                            clasificacion_ess = EXCLUDED.clasificacion_ess,
                            actualizado_en = NOW()
                        """,
                        fact_cuest_batch,
                    )
                    filas_cargadas += len(fact_cuest_batch)

                # 3. Procesar noches objetivas -> fact_sueno_noche (batch executemany)
                if participante_id is not None:
                    cur.execute(
                        "SELECT * FROM glympho_oltp.registro_sueno_noche WHERE participante_id = %s ORDER BY fecha",
                        (participante_id,),
                    )
                else:
                    cur.execute("SELECT * FROM glympho_oltp.registro_sueno_noche ORDER BY participante_id, fecha")

                fact_nights_batch: List[tuple] = []
                for n in cur.fetchall():
                    filas_leidas += 1
                    pid = n["participante_id"]
                    if pid not in part_map:
                        filas_rechazadas += 1
                        errors.append(f"Noche id={n['id']}: participante {pid} inexistente.")
                        continue

                    tib = float(n["tib_min"])
                    tst = float(n["tst_min"])
                    sol = float(n["sol_min"])
                    n1 = float(n["min_n1"])
                    n2 = float(n["min_n2"])
                    n3 = float(n["min_n3"])
                    rem = float(n["min_rem"])

                    if tst + sol > tib + 0.01 or abs((n1 + n2 + n3 + rem) - tst) > 1.0:
                        filas_rechazadas += 1
                        errors.append(f"Noche id={n['id']}: inconsistencia matematica de tiempos/fases.")
                        continue

                    obj = compute_objective_kpis(tib, tst, sol, n3)
                    tk = get_tiempo_key(n["fecha"])
                    hk = resolve_habito_key(pid, n["fecha"])
                    pm = part_map[pid]
                    fact_nights_batch.append(
                        (
                            tk, pm["participante_key"], pm["carrera_key"], hk,
                            tib, tst, sol, obj["waso_min"], int(n["despertares"]),
                            n1, n2, n3, rem, obj["se_pct"], obj["pct_n3"], obj["indice_glinfatico"],
                        )
                    )

                if fact_nights_batch:
                    cur.executemany(
                        """
                        INSERT INTO glympho_dw.fact_sueno_noche (
                            tiempo_key, participante_key, carrera_key, habito_key,
                            tib_min, tst_min, sol_min, waso_min, despertares,
                            min_n1, min_n2, min_n3, min_rem, se_pct, pct_n3, indice_glinfatico, actualizado_en
                        )
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                        ON CONFLICT (participante_key, tiempo_key) DO UPDATE SET
                            carrera_key = EXCLUDED.carrera_key,
                            habito_key = EXCLUDED.habito_key,
                            tib_min = EXCLUDED.tib_min,
                            tst_min = EXCLUDED.tst_min,
                            sol_min = EXCLUDED.sol_min,
                            waso_min = EXCLUDED.waso_min,
                            despertares = EXCLUDED.despertares,
                            min_n1 = EXCLUDED.min_n1,
                            min_n2 = EXCLUDED.min_n2,
                            min_n3 = EXCLUDED.min_n3,
                            min_rem = EXCLUDED.min_rem,
                            se_pct = EXCLUDED.se_pct,
                            pct_n3 = EXCLUDED.pct_n3,
                            indice_glinfatico = EXCLUDED.indice_glinfatico,
                            actualizado_en = NOW()
                        """,
                        fact_nights_batch,
                    )
                    filas_cargadas += len(fact_nights_batch)

                estado = "completado_con_alertas" if errors else "completado"
                cur.execute(
                    """
                    UPDATE glympho_dw.etl_ejecucion_log
                    SET fin = NOW(), estado = %s, filas_leidas = %s,
                        filas_cargadas = %s, filas_rechazadas = %s, detalle_errores = %s::jsonb
                    WHERE id = %s
                    """,
                    (estado, filas_leidas, filas_cargadas, filas_rechazadas, json.dumps(errors[:50]), log_id),
                )
            conn.commit()
            return {
                "log_id": log_id,
                "estado": estado,
                "filas_leidas": filas_leidas,
                "filas_cargadas": filas_cargadas,
                "filas_rechazadas": filas_rechazadas,
                "errores": errors[:20],
            }
        except Exception as exc:
            conn.rollback()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE glympho_dw.etl_ejecucion_log
                    SET fin = NOW(), estado = 'error', detalle_errores = %s::jsonb
                    WHERE id = %s
                    """,
                    (json.dumps([str(exc)]), log_id),
                )
            conn.commit()
            raise


if __name__ == "__main__":
    result = run_etl(origen="cli")
    print("ETL finalizado:", json.dumps(result, ensure_ascii=False, indent=2))
