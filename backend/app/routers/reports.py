from __future__ import annotations

import json
import time
from decimal import Decimal
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from app.core.database import get_db_conn
from app.core.security import get_current_user
from app.services.pdf_service import export_report_csv, export_report_pdf
from app.services.reports_service import generate_report_data
from app.services.s3_service import upload_bytes_to_s3

router = APIRouter(prefix="/api/reports", tags=["reports"])


class ExportRequest(BaseModel):
    report_type: str  # cohorte | dias_semana | habitos
    format: str       # pdf | csv
    filters: Dict[str, Any] = {}


@router.get("/preview/{report_type}")
def preview_report(
    report_type: str,
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    facultad: Optional[str] = Query(default=None),
    carrera: Optional[str] = Query(default=None),
    ciclo: Optional[int] = Query(default=None),
    user=Depends(get_current_user),
):
    if report_type not in ("cohorte", "dias_semana", "habitos"):
        raise HTTPException(status_code=400, detail="Tipo de reporte no valido.")
    filters = {"date_from": date_from, "date_to": date_to, "facultad": facultad, "carrera": carrera, "ciclo": ciclo}
    with get_db_conn() as conn:
        return generate_report_data(conn, report_type, filters)


@router.post("/export")
def export_report(body: ExportRequest, user=Depends(get_current_user)):
    if body.report_type not in ("cohorte", "dias_semana", "habitos"):
        raise HTTPException(status_code=400, detail="Tipo de reporte no valido.")
    if body.format not in ("pdf", "csv"):
        raise HTTPException(status_code=400, detail="Formato debe ser 'pdf' o 'csv'.")

    with get_db_conn() as conn:
        report = generate_report_data(conn, body.report_type, body.filters)
        if body.format == "pdf":
            content = export_report_pdf(report)
            media = "application/pdf"
            ext = "pdf"
        else:
            content = export_report_csv(report)
            media = "text/csv; charset=utf-8"
            ext = "csv"

        s3_key = upload_bytes_to_s3(f"reports/glymphocare_{body.report_type}.{ext}", content, media)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO glympho_oltp.reporte_generado (usuario_id, tipo, formato, parametros_json, s3_key)
                VALUES (%s, %s, %s, %s::jsonb, %s)
                """,
                (user["id"], body.report_type, body.format, json.dumps(body.filters), s3_key),
            )
        conn.commit()

    return Response(
        content=content,
        media_type=media,
        headers={"Content-Disposition": f"attachment; filename=glymphocare_{body.report_type}.{ext}"},
    )


@router.get("/history")
def report_history(user=Depends(get_current_user)):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT rg.id, rg.tipo, rg.formato, rg.parametros_json, rg.s3_key, rg.fecha,
                       u.nombre_display AS generado_por
                FROM glympho_oltp.reporte_generado rg
                LEFT JOIN glympho_oltp.usuario u ON u.id = rg.usuario_id
                ORDER BY rg.fecha DESC
                LIMIT 30
                """
            )
            rows = cur.fetchall()
    return [{**r, "fecha": r["fecha"].isoformat()} for r in rows]


SQL_EVIDENCE_QUERIES = {
    "q1_kpis": {
        "title": "Consulta 1 · Resumen de los 8 KPIs Oficiales (Data Mart)",
        "description": "Calcula PSQI, ESS, % malos dormidores, SE, SOL, WASO, Despertares, TST y %N3 desde fact_cuestionario y fact_sueno_noche.",
        "sql": """WITH ultimo_cuestionario AS (
    SELECT DISTINCT ON (fc.participante_key)
        fc.participante_key, fc.psqi_global, fc.ess_total, fc.clasificacion_psqi
    FROM glympho_dw.fact_cuestionario fc
    JOIN glympho_dw.dim_tiempo dt ON dt.tiempo_key = fc.tiempo_key
    ORDER BY fc.participante_key, dt.fecha DESC
)
SELECT
    COUNT(DISTINCT uc.participante_key) AS total_participantes,
    ROUND(AVG(uc.psqi_global)::numeric, 2) AS kpi1_psqi_promedio,
    ROUND(AVG(uc.ess_total)::numeric, 2) AS kpi2_ess_promedio,
    ROUND(100.0 * SUM(CASE WHEN uc.clasificacion_psqi = 'Mal dormidor' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS pct_malos_dormidores,
    ROUND(AVG(fsn.se_pct)::numeric, 1) AS kpi3_eficiencia_se_pct,
    ROUND(AVG(fsn.sol_min)::numeric, 1) AS kpi4_latencia_sol_min,
    ROUND(AVG(fsn.waso_min)::numeric, 1) AS kpi5_waso_min,
    ROUND(AVG(fsn.despertares)::numeric, 2) AS kpi6_despertares_prom,
    ROUND((AVG(fsn.tst_min) / 60.0)::numeric, 2) AS kpi7_tst_horas,
    ROUND(AVG(fsn.pct_n3)::numeric, 1) AS kpi8_sueno_profundo_n3_pct,
    ROUND(AVG(fsn.indice_glinfatico)::numeric, 3) AS metrica_derivada_ig
FROM ultimo_cuestionario uc
JOIN glympho_dw.fact_sueno_noche fsn ON fsn.participante_key = uc.participante_key;""",
    },
    "q2_cohorte": {
        "title": "Consulta 2 · Reporte de Cohorte RR-03 (ROLLUP Facultad y Carrera)",
        "description": "Clasifica buenos y malos dormidores por facultad/carrera con subtotales ROLLUP.",
        "sql": """WITH ultimo_psqi AS (
    SELECT DISTINCT ON (fc.participante_key)
        fc.participante_key, fc.carrera_key, fc.clasificacion_psqi
    FROM glympho_dw.fact_cuestionario fc
    JOIN glympho_dw.dim_tiempo dt ON dt.tiempo_key = fc.tiempo_key
    ORDER BY fc.participante_key, dt.fecha DESC
)
SELECT
    COALESCE(dc.facultad, '** TOTAL COHORTE **') AS facultad,
    COALESCE(dc.carrera, '-- Subtotal --') AS carrera,
    SUM(CASE WHEN up.clasificacion_psqi = 'Buen dormidor' THEN 1 ELSE 0 END) AS buenos_dormidores,
    SUM(CASE WHEN up.clasificacion_psqi = 'Mal dormidor' THEN 1 ELSE 0 END) AS malos_dormidores,
    COUNT(*) AS total_participantes,
    ROUND(100.0 * SUM(CASE WHEN up.clasificacion_psqi = 'Mal dormidor' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS pct_malos
FROM ultimo_psqi up
JOIN glympho_dw.dim_carrera dc ON dc.carrera_key = up.carrera_key
GROUP BY ROLLUP (dc.facultad, dc.carrera)
ORDER BY dc.facultad NULLS LAST, dc.carrera NULLS LAST;""",
    },
    "q3_dias_semana": {
        "title": "Consulta 3 · Indicadores por Día de la Semana (dim_tiempo)",
        "description": "Compara noches registradas, SOL, WASO, TST, SE%, %N3 y despertares entre semana vs fin de semana.",
        "sql": """SELECT
    CASE WHEN dt.es_fin_semana THEN 'Fin de semana' ELSE 'Entre semana' END AS grupo_dia,
    dt.dia_semana,
    COUNT(*) AS noches_registradas,
    ROUND(AVG(fsn.sol_min)::numeric, 1) AS sol_min,
    ROUND(AVG(fsn.waso_min)::numeric, 1) AS waso_min,
    ROUND(AVG(fsn.tst_min)::numeric, 1) AS tst_min,
    ROUND((AVG(fsn.tst_min) / NULLIF(AVG(fsn.sol_min + fsn.waso_min + fsn.tst_min), 0) * 100.0)::numeric, 1) AS se_pct,
    ROUND((AVG(fsn.min_n3) / NULLIF(AVG(fsn.tst_min), 0) * 100.0)::numeric, 1) AS pct_n3,
    ROUND(AVG(fsn.despertares)::numeric, 1) AS despertares
FROM glympho_dw.fact_sueno_noche fsn
JOIN glympho_dw.dim_tiempo dt ON dt.tiempo_key = fsn.tiempo_key
GROUP BY dt.es_fin_semana, dt.dia_semana_num, dt.dia_semana
ORDER BY dt.es_fin_semana, dt.dia_semana_num;""",
    },
    "q4_habitos": {
        "title": "Consulta 4 · Hábitos de Higiene vs KPIs RR-06 (dim_habito)",
        "description": "Contrasta métricas objetivas y PSQI según exposición a pantallas, cafeína, ejercicio y estrés.",
        "sql": """WITH ultimo_psqi AS (
    SELECT DISTINCT ON (fc.participante_key) fc.participante_key, fc.psqi_global
    FROM glympho_dw.fact_cuestionario fc
    JOIN glympho_dw.dim_tiempo dt ON dt.tiempo_key = fc.tiempo_key
    ORDER BY fc.participante_key, dt.fecha DESC
),
rp AS (
    SELECT fsn.participante_key,
        MAX(dh.uso_pantallas) AS uso_pantallas, MAX(dh.cafeina) AS cafeina,
        MAX(dh.ejercicio) AS ejercicio, MAX(dh.estres) AS estres,
        AVG(fsn.sol_min) AS sol_min, AVG(fsn.waso_min) AS waso_min,
        AVG(fsn.tst_min) AS tst_min, AVG(fsn.min_n3) AS min_n3
    FROM glympho_dw.fact_sueno_noche fsn
    JOIN glympho_dw.dim_habito dh ON dh.habito_key = fsn.habito_key
    GROUP BY fsn.participante_key
)
SELECT 'Pantallas' AS dimension, rp.uso_pantallas AS nivel, COUNT(*) AS n,
    ROUND(AVG(rp.sol_min)::numeric,1) AS sol_min, ROUND(AVG(rp.waso_min)::numeric,1) AS waso_min,
    ROUND(AVG(rp.tst_min)::numeric,1) AS tst_min,
    ROUND((AVG(rp.min_n3)/NULLIF(AVG(rp.tst_min),0)*100)::numeric,1) AS pct_n3,
    ROUND(AVG(up.psqi_global)::numeric,1) AS psqi_global
FROM rp JOIN ultimo_psqi up ON up.participante_key = rp.participante_key GROUP BY rp.uso_pantallas
UNION ALL
SELECT 'Cafeina', rp.cafeina, COUNT(*), ROUND(AVG(rp.sol_min)::numeric,1), ROUND(AVG(rp.waso_min)::numeric,1),
    ROUND(AVG(rp.tst_min)::numeric,1), ROUND((AVG(rp.min_n3)/NULLIF(AVG(rp.tst_min),0)*100)::numeric,1),
    ROUND(AVG(up.psqi_global)::numeric,1)
FROM rp JOIN ultimo_psqi up ON up.participante_key = rp.participante_key GROUP BY rp.cafeina
UNION ALL
SELECT 'Ejercicio', rp.ejercicio, COUNT(*), ROUND(AVG(rp.sol_min)::numeric,1), ROUND(AVG(rp.waso_min)::numeric,1),
    ROUND(AVG(rp.tst_min)::numeric,1), ROUND((AVG(rp.min_n3)/NULLIF(AVG(rp.tst_min),0)*100)::numeric,1),
    ROUND(AVG(up.psqi_global)::numeric,1)
FROM rp JOIN ultimo_psqi up ON up.participante_key = rp.participante_key GROUP BY rp.ejercicio;""",
    },
}


class SqlRunRequest(BaseModel):
    query_id: str


@router.get("/sql-evidence")
def list_sql_evidence(user=Depends(get_current_user)):
    return [
        {"id": k, "title": v["title"], "description": v["description"], "sql": v["sql"]}
        for k, v in SQL_EVIDENCE_QUERIES.items()
    ]


@router.post("/sql-evidence/run")
def run_sql_evidence(body: SqlRunRequest, user=Depends(get_current_user)):
    spec = SQL_EVIDENCE_QUERIES.get(body.query_id)
    if not spec:
        raise HTTPException(status_code=400, detail="Consulta SQL no autorizada.")

    t0 = time.perf_counter()
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(spec["sql"])
            raw_rows = cur.fetchall()
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 1)

    columns = list(raw_rows[0].keys()) if raw_rows else []
    clean_rows = []
    for r in raw_rows:
        clean_rows.append(
            {
                k: (float(v) if isinstance(v, Decimal) else v)
                for k, v in r.items()
            }
        )

    return {
        "query_id": body.query_id,
        "title": spec["title"],
        "sql": spec["sql"],
        "columns": columns,
        "rows": clean_rows,
        "row_count": len(clean_rows),
        "elapsed_ms": elapsed_ms,
        "engine": "Amazon RDS · PostgreSQL 16 (glympho_dw)",
    }
