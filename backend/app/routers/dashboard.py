from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.database import get_db_conn
from app.core.security import get_current_user
from app.services.reports_service import build_where_clause
from app.services.rules_engine import evaluate_rules
from app.services.stats_service import (
    boxplot_stats,
    compute_habit_correlations_and_findings,
    linear_regression_summary,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _extract_filters(
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    facultad: Optional[str] = Query(default=None),
    carrera: Optional[str] = Query(default=None),
    ciclo: Optional[int] = Query(default=None),
    pantallas: Optional[str] = Query(default=None),
    cafeina: Optional[str] = Query(default=None),
    ejercicio: Optional[str] = Query(default=None),
    estres: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    return {
        "date_from": date_from or None,
        "date_to": date_to or None,
        "facultad": facultad or None,
        "carrera": carrera or None,
        "ciclo": ciclo,
        "pantallas": pantallas or None,
        "cafeina": cafeina or None,
        "ejercicio": ejercicio or None,
        "estres": estres or None,
    }


@router.get("/filters")
def get_filter_options(user=Depends(get_current_user)):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT facultad, carrera FROM glympho_dw.dim_carrera ORDER BY facultad, carrera")
            carreras = cur.fetchall()
            cur.execute("SELECT DISTINCT ciclo FROM glympho_dw.dim_participante ORDER BY ciclo")
            ciclos = [r["ciclo"] for r in cur.fetchall()]
            cur.execute("SELECT MIN(fecha) AS min_fecha, MAX(fecha) AS max_fecha FROM glympho_dw.dim_tiempo")
            fechas = cur.fetchone()
    return {
        "facultades": sorted({c["facultad"] for c in carreras}),
        "carreras": carreras,
        "ciclos": ciclos,
        "min_fecha": str(fechas["min_fecha"]) if fechas and fechas["min_fecha"] else None,
        "max_fecha": str(fechas["max_fecha"]) if fechas and fechas["max_fecha"] else None,
    }


@router.get("/executive")
def executive_dashboard(filters: Dict[str, Any] = Depends(_extract_filters), user=Depends(get_current_user)):
    where_sql, params = build_where_clause(filters)
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                WITH ult AS (
                    SELECT DISTINCT ON (fc.participante_key)
                        fc.participante_key, fc.psqi_global, fc.ess_total, fc.clasificacion_psqi
                    FROM glympho_dw.fact_cuestionario fc
                    JOIN glympho_dw.dim_tiempo dt ON dt.tiempo_key = fc.tiempo_key
                    JOIN glympho_dw.dim_participante dp ON dp.participante_key = fc.participante_key
                    JOIN glympho_dw.dim_carrera dc ON dc.carrera_key = fc.carrera_key
                    JOIN glympho_dw.dim_habito dh ON dh.habito_key = fc.habito_key
                    {where_sql}
                    ORDER BY fc.participante_key, dt.fecha DESC
                )
                SELECT
                    COUNT(*) AS participantes,
                    ROUND(AVG(psqi_global)::numeric, 2) AS psqi_prom,
                    ROUND(AVG(ess_total)::numeric, 2) AS ess_prom,
                    SUM(CASE WHEN clasificacion_psqi = 'Buen dormidor' THEN 1 ELSE 0 END) AS buenos,
                    SUM(CASE WHEN clasificacion_psqi = 'Mal dormidor' THEN 1 ELSE 0 END) AS malos
                FROM ult
                """,
                params,
            )
            subj = cur.fetchone()

            cur.execute(
                f"""
                SELECT
                    COUNT(*) AS noches,
                    COUNT(DISTINCT fsn.participante_key) AS participantes_obj,
                    ROUND(AVG(fsn.se_pct)::numeric, 1) AS se_prom,
                    ROUND(AVG(fsn.sol_min)::numeric, 1) AS sol_prom,
                    ROUND(AVG(fsn.waso_min)::numeric, 1) AS waso_prom,
                    ROUND(AVG(fsn.tst_min)::numeric, 1) AS tst_min_prom,
                    ROUND(AVG(fsn.pct_n3)::numeric, 1) AS pct_n3_prom,
                    ROUND(AVG(fsn.despertares)::numeric, 2) AS despertares_prom,
                    ROUND(AVG(fsn.indice_glinfatico)::numeric, 3) AS ig_prom
                FROM glympho_dw.fact_sueno_noche fsn
                JOIN glympho_dw.dim_tiempo dt ON dt.tiempo_key = fsn.tiempo_key
                JOIN glympho_dw.dim_participante dp ON dp.participante_key = fsn.participante_key
                JOIN glympho_dw.dim_carrera dc ON dc.carrera_key = fsn.carrera_key
                JOIN glympho_dw.dim_habito dh ON dh.habito_key = fsn.habito_key
                {where_sql}
                """,
                params,
            )
            obj = cur.fetchone()

            # Tendencia diaria (noches objetivas)
            cur.execute(
                f"""
                SELECT
                    dt.fecha,
                    ROUND(AVG(fsn.se_pct)::numeric, 1) AS se_pct,
                    ROUND(AVG(fsn.pct_n3)::numeric, 1) AS pct_n3,
                    ROUND((AVG(fsn.tst_min) / 60.0)::numeric, 2) AS tst_h
                FROM glympho_dw.fact_sueno_noche fsn
                JOIN glympho_dw.dim_tiempo dt ON dt.tiempo_key = fsn.tiempo_key
                JOIN glympho_dw.dim_participante dp ON dp.participante_key = fsn.participante_key
                JOIN glympho_dw.dim_carrera dc ON dc.carrera_key = fsn.carrera_key
                JOIN glympho_dw.dim_habito dh ON dh.habito_key = fsn.habito_key
                {where_sql}
                GROUP BY dt.fecha
                ORDER BY dt.fecha
                """,
                params,
            )
            trend_nights = [{"fecha": str(r["fecha"]), "se_pct": float(r["se_pct"]), "pct_n3": float(r["pct_n3"]), "tst_h": float(r["tst_h"])} for r in cur.fetchall()]

            # Heatmap: dia de semana x Facultad -> %N3 y TST
            cur.execute(
                f"""
                SELECT
                    dc.facultad,
                    dt.dia_semana_num,
                    dt.dia_semana,
                    ROUND(AVG(fsn.pct_n3)::numeric, 1) AS pct_n3,
                    ROUND(AVG(fsn.tst_min)::numeric, 0) AS tst_min
                FROM glympho_dw.fact_sueno_noche fsn
                JOIN glympho_dw.dim_tiempo dt ON dt.tiempo_key = fsn.tiempo_key
                JOIN glympho_dw.dim_participante dp ON dp.participante_key = fsn.participante_key
                JOIN glympho_dw.dim_carrera dc ON dc.carrera_key = fsn.carrera_key
                JOIN glympho_dw.dim_habito dh ON dh.habito_key = fsn.habito_key
                {where_sql}
                GROUP BY dc.facultad, dt.dia_semana_num, dt.dia_semana
                ORDER BY dc.facultad, dt.dia_semana_num
                """,
                params,
            )
            heatmap = [
                {
                    "facultad": r["facultad"],
                    "dia_num": r["dia_semana_num"],
                    "dia": r["dia_semana"],
                    "pct_n3": float(r["pct_n3"]),
                    "tst_min": float(r["tst_min"]),
                }
                for r in cur.fetchall()
            ]

            cur.execute("SELECT * FROM glympho_oltp.recomendacion_regla WHERE activo = TRUE")
            rules = cur.fetchall()

    n_part = int(subj["participantes"] or 0)
    buenos = int(subj["buenos"] or 0)
    malos = int(subj["malos"] or 0)
    pct_malos = round(malos / n_part * 100.0, 1) if n_part else 0.0

    kpis = {
        "PSQI": float(subj["psqi_prom"]) if subj["psqi_prom"] is not None else None,
        "ESS": float(subj["ess_prom"]) if subj["ess_prom"] is not None else None,
        "SE": float(obj["se_prom"]) if obj["se_prom"] is not None else None,
        "SOL": float(obj["sol_prom"]) if obj["sol_prom"] is not None else None,
        "WASO": float(obj["waso_prom"]) if obj["waso_prom"] is not None else None,
        "TST": float(obj["tst_min_prom"]) if obj["tst_min_prom"] is not None else None,
        "PCT_N3": float(obj["pct_n3_prom"]) if obj["pct_n3_prom"] is not None else None,
        "DESPERTARES": float(obj["despertares_prom"]) if obj["despertares_prom"] is not None else None,
    }
    alerts = evaluate_rules(kpis, rules)

    return {
        "n_participantes": n_part,
        "n_noches": int(obj["noches"] or 0),
        "kpis": {
            **kpis,
            "pct_malos_dormidores": pct_malos,
            "buenos_dormidores": buenos,
            "malos_dormidores": malos,
            "indice_glinfatico": float(obj["ig_prom"]) if obj["ig_prom"] is not None else None,
        },
        "trend_nights": trend_nights,
        "distribution": [
            {"name": "Buen dormidor (PSQI <= 5)", "value": buenos},
            {"name": "Mal dormidor (PSQI > 5)", "value": malos},
        ],
        "heatmap": heatmap,
        "alerts": alerts,
    }


@router.get("/subjective")
def subjective_quality(filters: Dict[str, Any] = Depends(_extract_filters), user=Depends(get_current_user)):
    where_sql, params = build_where_clause(filters)
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                WITH ult AS (
                    SELECT DISTINCT ON (fc.participante_key)
                        fc.*, dp.codigo, dp.edad, dp.rango_edad, dp.ciclo,
                        dc.facultad, dc.carrera, dt.fecha AS fecha_eval
                    FROM glympho_dw.fact_cuestionario fc
                    JOIN glympho_dw.dim_tiempo dt ON dt.tiempo_key = fc.tiempo_key
                    JOIN glympho_dw.dim_participante dp ON dp.participante_key = fc.participante_key
                    JOIN glympho_dw.dim_carrera dc ON dc.carrera_key = fc.carrera_key
                    JOIN glympho_dw.dim_habito dh ON dh.habito_key = fc.habito_key
                    {where_sql}
                    ORDER BY fc.participante_key, dt.fecha DESC
                )
                SELECT * FROM ult ORDER BY psqi_global DESC, ess_total DESC
                """,
                params,
            )
            rows = cur.fetchall()

            # Tendencia longitudinal por mes de evaluacion
            cur.execute(
                f"""
                SELECT
                    TO_CHAR(dt.fecha, 'YYYY-MM') AS periodo,
                    ROUND(AVG(fc.psqi_global)::numeric, 2) AS psqi_prom,
                    ROUND(AVG(fc.ess_total)::numeric, 2) AS ess_prom,
                    COUNT(*) AS evaluaciones
                FROM glympho_dw.fact_cuestionario fc
                JOIN glympho_dw.dim_tiempo dt ON dt.tiempo_key = fc.tiempo_key
                JOIN glympho_dw.dim_participante dp ON dp.participante_key = fc.participante_key
                JOIN glympho_dw.dim_carrera dc ON dc.carrera_key = fc.carrera_key
                JOIN glympho_dw.dim_habito dh ON dh.habito_key = fc.habito_key
                {where_sql}
                GROUP BY TO_CHAR(dt.fecha, 'YYYY-MM')
                ORDER BY periodo
                """,
                params,
            )
            longitudinal = [
                {"periodo": r["periodo"], "psqi_prom": float(r["psqi_prom"]), "ess_prom": float(r["ess_prom"]), "n": int(r["evaluaciones"])}
                for r in cur.fetchall()
            ]

    n = len(rows)
    comp_keys = [
        ("c1_calidad", "C1 Calidad"),
        ("c2_latencia", "C2 Latencia"),
        ("c3_duracion", "C3 Duracion"),
        ("c4_eficiencia", "C4 Eficiencia"),
        ("c5_alteraciones", "C5 Alteraciones"),
        ("c6_medicacion", "C6 Medicacion"),
        ("c7_disfuncion", "C7 Disfuncion"),
    ]
    radar = [
        {
            "component": label,
            "cohorte": round(sum(float(r[col]) for r in rows) / n, 2) if n else 0.0,
            "ideal": 0.5,
        }
        for col, label in comp_keys
    ]

    by_fac: Dict[str, list[float]] = {}
    for r in rows:
        by_fac.setdefault(r["facultad"], []).append(float(r["psqi_global"]))

    faculty_summary = [
        {
            "facultad": fac,
            "psqi_prom": round(sum(vals) / len(vals), 2),
            "n": len(vals),
            "boxplot": boxplot_stats(vals),
        }
        for fac, vals in by_fac.items()
    ]

    top_risk = [
        {
            "codigo": r["codigo"],
            "facultad": r["facultad"],
            "carrera": r["carrera"],
            "ciclo": r["ciclo"],
            "edad": r["edad"],
            "psqi_global": r["psqi_global"],
            "ess_total": r["ess_total"],
            "clasificacion_psqi": r["clasificacion_psqi"],
            "fecha_eval": str(r["fecha_eval"]),
        }
        for r in rows[:10]
    ]

    return {
        "n_participantes": n,
        "radar": radar,
        "faculty_summary": faculty_summary,
        "longitudinal": longitudinal,
        "top_risk": top_risk,
    }


@router.get("/glymphatic")
def glymphatic_analysis(filters: Dict[str, Any] = Depends(_extract_filters), user=Depends(get_current_user)):
    where_sql, params = build_where_clause(filters)
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                WITH ult_psqi AS (
                    SELECT DISTINCT ON (fc.participante_key)
                        fc.participante_key, fc.psqi_global, fc.ess_total
                    FROM glympho_dw.fact_cuestionario fc
                    JOIN glympho_dw.dim_tiempo dt ON dt.tiempo_key = fc.tiempo_key
                    ORDER BY fc.participante_key, dt.fecha DESC
                )
                SELECT
                    dp.codigo,
                    dc.facultad,
                    dc.carrera,
                    ROUND(AVG(fsn.min_n1)::numeric, 1) AS n1,
                    ROUND(AVG(fsn.min_n2)::numeric, 1) AS n2,
                    ROUND(AVG(fsn.min_n3)::numeric, 1) AS n3,
                    ROUND(AVG(fsn.min_rem)::numeric, 1) AS rem,
                    ROUND(AVG(fsn.tst_min)::numeric, 1) AS tst_min,
                    ROUND(AVG(fsn.se_pct)::numeric, 1) AS se_pct,
                    ROUND(AVG(fsn.sol_min)::numeric, 1) AS sol_min,
                    ROUND(AVG(fsn.pct_n3)::numeric, 1) AS pct_n3,
                    ROUND(AVG(fsn.indice_glinfatico)::numeric, 3) AS ig,
                    ROUND((SUM(fsn.min_n3) / 60.0)::numeric, 1) AS horas_n3_acum,
                    COALESCE(MAX(up.psqi_global), 0) AS psqi_global
                FROM glympho_dw.fact_sueno_noche fsn
                JOIN glympho_dw.dim_tiempo dt ON dt.tiempo_key = fsn.tiempo_key
                JOIN glympho_dw.dim_participante dp ON dp.participante_key = fsn.participante_key
                JOIN glympho_dw.dim_carrera dc ON dc.carrera_key = fsn.carrera_key
                JOIN glympho_dw.dim_habito dh ON dh.habito_key = fsn.habito_key
                LEFT JOIN ult_psqi up ON up.participante_key = fsn.participante_key
                {where_sql}
                GROUP BY dp.codigo, dc.facultad, dc.carrera
                ORDER BY pct_n3 DESC
                """,
                params,
            )
            parts = cur.fetchall()

    n = len(parts)
    if n == 0:
        return {"n_participantes": 0, "architecture": [], "ig_prom": 0, "horas_n3_prom": 0, "scatter": [], "regression": {}, "quadrant": []}

    avg_n1 = round(sum(float(p["n1"]) for p in parts) / n, 1)
    avg_n2 = round(sum(float(p["n2"]) for p in parts) / n, 1)
    avg_n3 = round(sum(float(p["n3"]) for p in parts) / n, 1)
    avg_rem = round(sum(float(p["rem"]) for p in parts) / n, 1)
    avg_tst = avg_n1 + avg_n2 + avg_n3 + avg_rem
    ig_prom = round(sum(float(p["ig"]) for p in parts) / n, 3)
    horas_n3_prom = round(sum(float(p["horas_n3_acum"]) for p in parts) / n, 1)
    pct_n3_prom = round(sum(float(p["pct_n3"]) for p in parts) / n, 1)

    xs = [float(p["pct_n3"]) for p in parts]
    ys = [float(p["psqi_global"]) for p in parts]
    reg = linear_regression_summary(xs, ys)

    return {
        "n_participantes": n,
        "ig_prom": ig_prom,
        "pct_n3_prom": pct_n3_prom,
        "horas_n3_acum_prom": horas_n3_prom,
        "architecture": [
            {"fase": "N1 (Transicion)", "minutos": avg_n1, "pct": round(avg_n1 / avg_tst * 100, 1), "potencial_glinfatico": "Bajo"},
            {"fase": "N2 (Sueno ligero)", "minutos": avg_n2, "pct": round(avg_n2 / avg_tst * 100, 1), "potencial_glinfatico": "Medio"},
            {"fase": "N3 (Sueno profundo)", "minutos": avg_n3, "pct": round(avg_n3 / avg_tst * 100, 1), "potencial_glinfatico": "Alto (Limpieza glinfatica)"},
            {"fase": "REM (Consolidacion)", "minutos": avg_rem, "pct": round(avg_rem / avg_tst * 100, 1), "potencial_glinfatico": "Bajo-Medio"},
        ],
        "scatter": [
            {
                "codigo": p["codigo"],
                "facultad": p["facultad"],
                "pct_n3": float(p["pct_n3"]),
                "psqi_global": float(p["psqi_global"]),
                "se_pct": float(p["se_pct"]),
                "ig": float(p["ig"]),
            }
            for p in parts
        ],
        "regression": reg,
    }


@router.get("/habits")
def habits_and_correlations(filters: Dict[str, Any] = Depends(_extract_filters), user=Depends(get_current_user)):
    where_sql, params = build_where_clause(filters)
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                WITH ult_psqi AS (
                    SELECT DISTINCT ON (fc.participante_key)
                        fc.participante_key, fc.psqi_global, fc.ess_total
                    FROM glympho_dw.fact_cuestionario fc
                    JOIN glympho_dw.dim_tiempo dt ON dt.tiempo_key = fc.tiempo_key
                    ORDER BY fc.participante_key, dt.fecha DESC
                )
                SELECT
                    dp.codigo,
                    (ARRAY_AGG(dh.uso_pantallas ORDER BY dt.fecha DESC))[1] AS uso_pantallas,
                    (ARRAY_AGG(dh.cafeina ORDER BY dt.fecha DESC))[1] AS cafeina,
                    (ARRAY_AGG(dh.ejercicio ORDER BY dt.fecha DESC))[1] AS ejercicio,
                    (ARRAY_AGG(dh.estres ORDER BY dt.fecha DESC))[1] AS estres,
                    (ARRAY_AGG(dh.regularidad_horarios ORDER BY dt.fecha DESC))[1] AS regularidad_horarios,
                    AVG(fsn.sol_min) AS sol_min,
                    AVG(fsn.waso_min) AS waso_min,
                    AVG(fsn.se_pct) AS se_pct,
                    AVG(fsn.pct_n3) AS pct_n3,
                    AVG(fsn.tst_min) AS tst_min,
                    COALESCE(MAX(up.psqi_global), 0) AS psqi_global,
                    COALESCE(MAX(up.ess_total), 0) AS ess_total
                FROM glympho_dw.fact_sueno_noche fsn
                JOIN glympho_dw.dim_tiempo dt ON dt.tiempo_key = fsn.tiempo_key
                JOIN glympho_dw.dim_participante dp ON dp.participante_key = fsn.participante_key
                JOIN glympho_dw.dim_carrera dc ON dc.carrera_key = fsn.carrera_key
                JOIN glympho_dw.dim_habito dh ON dh.habito_key = fsn.habito_key
                LEFT JOIN ult_psqi up ON up.participante_key = fsn.participante_key
                {where_sql}
                GROUP BY dp.codigo
                """,
                params,
            )
            rows = cur.fetchall()

    stats_res = compute_habit_correlations_and_findings(rows)

    def group_comparison(field: str, options: list[tuple[str, str]], metric: str):
        out = []
        for val, label in options:
            vals = [float(r[metric]) for r in rows if r[field] == val]
            if vals:
                out.append({
                    "label": label,
                    "n": len(vals),
                    "mean": round(sum(vals) / len(vals), 2),
                    "boxplot": boxplot_stats(vals),
                })
        return out

    return {
        "n_participantes": len(rows),
        **stats_res,
        "comparisons": {
            "pantallas_sol": group_comparison("uso_pantallas", [(">1h", "Pantallas > 1h"), ("<=1h", "Pantallas <= 1h")], "sol_min"),
            "cafeina_psqi": group_comparison("cafeina", [("despues_14h", "Cafeina > 14h"), ("antes_14h_o_ninguna", "Antes 14h / Ninguna")], "psqi_global"),
            "ejercicio_n3": group_comparison("ejercicio", [(">=3_dias", "Ejercicio >= 3 d/sem"), ("<3_dias", "Ejercicio < 3 d/sem")], "pct_n3"),
            "estres_waso": group_comparison("estres", [("alto", "Estres Alto"), ("medio", "Estres Medio"), ("bajo", "Estres Bajo")], "waso_min"),
        },
    }


@router.get("/participants")
def list_participants(q: Optional[str] = Query(default=None), user=Depends(get_current_user)):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            like = f"%{q.strip()}%" if q else "%"
            cur.execute(
                """
                WITH ult AS (
                    SELECT DISTINCT ON (fc.participante_key)
                        fc.participante_key, fc.psqi_global, fc.ess_total, fc.clasificacion_psqi
                    FROM glympho_dw.fact_cuestionario fc
                    JOIN glympho_dw.dim_tiempo dt ON dt.tiempo_key = fc.tiempo_key
                    ORDER BY fc.participante_key, dt.fecha DESC
                )
                SELECT
                    dp.codigo, dp.edad, dp.sexo, dp.ciclo,
                    dc.facultad, dc.carrera,
                    COALESCE(u.psqi_global, 0) AS psqi_global,
                    COALESCE(u.ess_total, 0) AS ess_total,
                    COALESCE(u.clasificacion_psqi, 'Sin eval') AS clasificacion_psqi,
                    ROUND(AVG(fsn.pct_n3)::numeric, 1) AS pct_n3_prom,
                    ROUND(AVG(fsn.se_pct)::numeric, 1) AS se_prom,
                    COUNT(fsn.sueno_noche_key) AS noches
                FROM glympho_dw.dim_participante dp
                LEFT JOIN glympho_dw.fact_sueno_noche fsn ON fsn.participante_key = dp.participante_key
                LEFT JOIN glympho_dw.dim_carrera dc ON dc.carrera_key = COALESCE(fsn.carrera_key, (SELECT carrera_key FROM glympho_dw.fact_cuestionario WHERE participante_key = dp.participante_key LIMIT 1))
                LEFT JOIN ult u ON u.participante_key = dp.participante_key
                WHERE dp.codigo ILIKE %s OR COALESCE(dc.carrera,'') ILIKE %s OR COALESCE(dc.facultad,'') ILIKE %s
                GROUP BY dp.participante_key, dp.codigo, dp.edad, dp.sexo, dp.ciclo, dc.facultad, dc.carrera, u.psqi_global, u.ess_total, u.clasificacion_psqi
                ORDER BY dp.codigo
                """,
                (like, like, like),
            )
            return cur.fetchall()


@router.get("/participants/{codigo}")
def participant_detail(codigo: str, user=Depends(get_current_user)):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT dp.*, p.facultad, p.carrera
                FROM glympho_dw.dim_participante dp
                JOIN glympho_oltp.participante p ON p.id = dp.participante_id_oltp
                WHERE dp.codigo = %s
                """,
                (codigo,),
            )
            part = cur.fetchone()
            if not part:
                raise HTTPException(status_code=404, detail="Participante no encontrado.")

            pk = part["participante_key"]
            cur.execute(
                """
                SELECT dt.fecha, fc.c1_calidad, fc.c2_latencia, fc.c3_duracion, fc.c4_eficiencia,
                       fc.c5_alteraciones, fc.c6_medicacion, fc.c7_disfuncion,
                       fc.psqi_global, fc.ess_total, fc.clasificacion_psqi, fc.clasificacion_ess,
                       dh.uso_pantallas, dh.cafeina, dh.ejercicio, dh.estres, dh.regularidad_horarios
                FROM glympho_dw.fact_cuestionario fc
                JOIN glympho_dw.dim_tiempo dt ON dt.tiempo_key = fc.tiempo_key
                JOIN glympho_dw.dim_habito dh ON dh.habito_key = fc.habito_key
                WHERE fc.participante_key = %s
                ORDER BY dt.fecha
                """,
                (pk,),
            )
            evals = cur.fetchall()

            cur.execute(
                """
                SELECT dt.fecha, dt.dia_semana, fsn.tib_min, fsn.tst_min, fsn.sol_min,
                       fsn.waso_min, fsn.despertares, fsn.min_n1, fsn.min_n2, fsn.min_n3, fsn.min_rem,
                       fsn.se_pct, fsn.pct_n3, fsn.indice_glinfatico
                FROM glympho_dw.fact_sueno_noche fsn
                JOIN glympho_dw.dim_tiempo dt ON dt.tiempo_key = fsn.tiempo_key
                WHERE fsn.participante_key = %s
                ORDER BY dt.fecha
                """,
                (pk,),
            )
            nights = cur.fetchall()

            cur.execute("SELECT * FROM glympho_oltp.recomendacion_regla WHERE activo = TRUE")
            rules = cur.fetchall()

    latest_eval = evals[-1] if evals else {}
    n_nights = len(nights)
    avg_se = round(sum(float(n["se_pct"]) for n in nights) / n_nights, 1) if n_nights else None
    avg_sol = round(sum(float(n["sol_min"]) for n in nights) / n_nights, 1) if n_nights else None
    avg_waso = round(sum(float(n["waso_min"]) for n in nights) / n_nights, 1) if n_nights else None
    avg_tst = round(sum(float(n["tst_min"]) for n in nights) / n_nights, 1) if n_nights else None
    avg_n3 = round(sum(float(n["pct_n3"]) for n in nights) / n_nights, 1) if n_nights else None
    avg_desp = round(sum(float(n["despertares"]) for n in nights) / n_nights, 1) if n_nights else None
    avg_ig = round(sum(float(n["indice_glinfatico"]) for n in nights) / n_nights, 3) if n_nights else None

    kpis = {
        "PSQI": latest_eval.get("psqi_global"),
        "ESS": latest_eval.get("ess_total"),
        "SE": avg_se,
        "SOL": avg_sol,
        "WASO": avg_waso,
        "TST": avg_tst,
        "PCT_N3": avg_n3,
        "DESPERTARES": avg_desp,
    }
    alerts = evaluate_rules(kpis, rules)

    return {
        "participante": part,
        "kpis": {**kpis, "indice_glinfatico": avg_ig},
        "habitos_actuales": {
            "uso_pantallas": latest_eval.get("uso_pantallas"),
            "cafeina": latest_eval.get("cafeina"),
            "ejercicio": latest_eval.get("ejercicio"),
            "estres": latest_eval.get("estres"),
            "regularidad_horarios": latest_eval.get("regularidad_horarios"),
        },
        "evaluaciones": [
            {**e, "fecha": str(e["fecha"])} for e in evals
        ],
        "noches": [
            {
                "fecha": str(n["fecha"]),
                "dia_semana": n["dia_semana"],
                "tib_min": float(n["tib_min"]),
                "tst_min": float(n["tst_min"]),
                "sol_min": float(n["sol_min"]),
                "waso_min": float(n["waso_min"]),
                "despertares": int(n["despertares"]),
                "min_n3": float(n["min_n3"]),
                "se_pct": float(n["se_pct"]),
                "pct_n3": float(n["pct_n3"]),
                "ig": float(n["indice_glinfatico"]),
            }
            for n in nights
        ],
        "alerts": alerts,
    }


class SimulateHabitsRequest(BaseModel):
    pantallas: str = "<=1h"
    cafeina: str = "antes_14h_o_ninguna"
    ejercicio: str = ">=3_dias"
    estres: str = "bajo"
    wake_time: str = "07:00"


@router.post("/simulate-habits")
def simulate_habits(body: SimulateHabitsRequest, user=Depends(get_current_user)):
    """
    Simulador empirico de higiene del sueno y horario de descanso (sin modelos ML).
    Calcula la proyeccion aditiva de deltas reales medidos en el Data Mart (glympho_dw)
    y ajusta el horario recomendado para mitigar la deuda semanal de sueno.
    """
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH ult_psqi AS (
                    SELECT DISTINCT ON (fc.participante_key) fc.participante_key, fc.psqi_global
                    FROM glympho_dw.fact_cuestionario fc
                    JOIN glympho_dw.dim_tiempo dt ON dt.tiempo_key = fc.tiempo_key
                    ORDER BY fc.participante_key, dt.fecha DESC
                ),
                rp AS (
                    SELECT fsn.participante_key,
                        (ARRAY_AGG(dh.uso_pantallas ORDER BY dt.fecha DESC))[1] AS uso_pantallas,
                        (ARRAY_AGG(dh.cafeina ORDER BY dt.fecha DESC))[1] AS cafeina,
                        (ARRAY_AGG(dh.ejercicio ORDER BY dt.fecha DESC))[1] AS ejercicio,
                        (ARRAY_AGG(dh.estres ORDER BY dt.fecha DESC))[1] AS estres,
                        AVG(fsn.sol_min) AS sol, AVG(fsn.waso_min) AS waso,
                        AVG(fsn.tst_min) AS tst, AVG(fsn.se_pct) AS se, AVG(fsn.pct_n3) AS pct_n3
                    FROM glympho_dw.fact_sueno_noche fsn
                    JOIN glympho_dw.dim_tiempo dt ON dt.tiempo_key = fsn.tiempo_key
                    JOIN glympho_dw.dim_habito dh ON dh.habito_key = fsn.habito_key
                    GROUP BY fsn.participante_key
                )
                SELECT rp.*, COALESCE(up.psqi_global, 6) AS psqi
                FROM rp LEFT JOIN ult_psqi up ON up.participante_key = rp.participante_key
                """
            )
            rows = cur.fetchall()

    n = len(rows)
    if n == 0:
        raise HTTPException(status_code=400, detail="Sin datos suficientes en el Data Mart.")

    def avg_col(subset, col):
        return sum(float(r[col]) for r in subset) / len(subset) if subset else 0.0

    base = {
        "sol_min": round(avg_col(rows, "sol"), 1),
        "waso_min": round(avg_col(rows, "waso"), 1),
        "tst_min": round(avg_col(rows, "tst"), 1),
        "se_pct": round(avg_col(rows, "se"), 1),
        "pct_n3": round(avg_col(rows, "pct_n3"), 1),
        "psqi": round(avg_col(rows, "psqi"), 2),
    }

    # Deltas empiricos reales por habito respecto a la media de cohorte (ponderado 0.45 para evitar sobreestimacion aditiva)
    specs = [
        ("uso_pantallas", body.pantallas),
        ("cafeina", body.cafeina),
        ("ejercicio", body.ejercicio),
        ("estres", body.estres),
    ]
    deltas = {k: 0.0 for k in base}
    for field, target in specs:
        sub = [r for r in rows if r[field] == target]
        if sub:
            for k in base:
                deltas[k] += (avg_col(sub, k if k not in ("sol_min", "waso_min", "tst_min", "se_pct") else k.replace("_min", "").replace("_pct", "")) - base[k]) * 0.45

    proj_sol = round(max(8.0, min(60.0, base["sol_min"] + deltas["sol_min"])), 1)
    proj_waso = round(max(12.0, min(80.0, base["waso_min"] + deltas["waso_min"])), 1)
    proj_tst = round(max(300.0, min(510.0, base["tst_min"] + deltas["tst_min"])), 1)
    proj_tib = proj_tst + proj_sol + proj_waso
    proj_se = round((proj_tst / proj_tib) * 100.0, 1)
    proj_n3 = round(max(10.0, min(28.0, base["pct_n3"] + deltas["pct_n3"])), 1)
    proj_psqi = round(max(1.5, min(18.0, base["psqi"] + deltas["psqi"])), 2)

    deuda_sem_base = round(max(0.0, 7.0 * (420.0 - base["tst_min"]) / 60.0), 1)
    deuda_sem_proj = round(max(0.0, 7.0 * (420.0 - proj_tst) / 60.0), 1)

    # Calculo de horario exacto de descanso desde wake_time (meta: 7.5 h = 450 min + SOL + WASO est.)
    try:
        wh, wm = [int(x) for x in body.wake_time.split(":")[:2]]
    except Exception:
        wh, wm = 7, 0
    wake_total = wh * 60 + wm
    needed_tib = int(round(450 + proj_sol + min(30.0, proj_waso * 0.5)))
    bed_total = (wake_total - needed_tib) % (24 * 60)
    screen_off_total = (bed_total - 60) % (24 * 60)

    def fmt_hhmm(mins: int) -> str:
        return f"{mins // 60:02d}:{mins % 60:02d}"

    return {
        "n_referencia": n,
        "linea_base": base,
        "proyeccion": {
            "sol_min": proj_sol,
            "waso_min": proj_waso,
            "tst_min": proj_tst,
            "se_pct": proj_se,
            "pct_n3": proj_n3,
            "psqi": proj_psqi,
        },
        "deuda_cognitiva": {
            "deuda_semanal_base_h": deuda_sem_base,
            "deuda_semanal_proyectada_h": deuda_sem_proj,
            "alerta": "Deuda cognitiva activa (< 7 h/noche)" if base["tst_min"] < 420 else "Duración dentro de meta",
        },
        "horario_recomendado": {
            "hora_levantarse": fmt_hhmm(wake_total),
            "hora_acostarse": fmt_hhmm(bed_total),
            "hora_apagar_pantallas": fmt_hhmm(screen_off_total),
            "hora_limite_cafeina": "14:00",
        },
    }
