"""Constructor de los 3 reportes clinicos oficiales desde el Data Mart (glympho_dw)."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import psycopg


def build_where_clause(filters: Dict[str, Any], table_alias: str = "f") -> Tuple[str, List[Any]]:
    clauses: List[str] = []
    params: List[Any] = []

    if filters.get("date_from"):
        clauses.append("dt.fecha >= %s")
        params.append(filters["date_from"])
    if filters.get("date_to"):
        clauses.append("dt.fecha <= %s")
        params.append(filters["date_to"])
    if filters.get("facultad"):
        clauses.append("dc.facultad = %s")
        params.append(filters["facultad"])
    if filters.get("carrera"):
        clauses.append("dc.carrera = %s")
        params.append(filters["carrera"])
    if filters.get("ciclo"):
        clauses.append("dp.ciclo = %s")
        params.append(int(filters["ciclo"]))
    if filters.get("pantallas"):
        clauses.append("dh.uso_pantallas = %s")
        params.append(filters["pantallas"])
    if filters.get("cafeina"):
        clauses.append("dh.cafeina = %s")
        params.append(filters["cafeina"])
    if filters.get("ejercicio"):
        clauses.append("dh.ejercicio = %s")
        params.append(filters["ejercicio"])
    if filters.get("estres"):
        clauses.append("dh.estres = %s")
        params.append(filters["estres"])

    if not clauses:
        return "", []
    return "WHERE " + " AND ".join(clauses), params


def _calc_night_row(label: str, row_type: str, nights: int, sol: float, waso: float, tst: float, min_n3: float, desp: float) -> Dict[str, Any]:
    tib = sol + waso + tst
    se = (tst / tib * 100.0) if tib > 0 else 0.0
    pct_n3 = (min_n3 / tst * 100.0) if tst > 0 else 0.0
    values = [int(nights), round(sol, 1), round(waso, 1), round(tst, 1), round(se, 1), round(pct_n3, 1), round(desp, 1)]
    bad = [
        False,
        sol > 20.0,
        waso > 40.0,
        tst < 420.0,
        se < 85.0,
        False,
        False,
    ]
    return {"type": row_type, "label": label, "values": values, "bad": bad}


def generate_report_data(conn: psycopg.Connection, report_type: str, filters: Dict[str, Any]) -> Dict[str, Any]:
    where_sql, params = build_where_clause(filters)

    with conn.cursor() as cur:
        if report_type == "cohorte":
            cur.execute(
                f"""
                WITH ultimo_psqi AS (
                    SELECT DISTINCT ON (fc.participante_key)
                        fc.participante_key,
                        dc.facultad,
                        dc.carrera,
                        fc.clasificacion_psqi
                    FROM glympho_dw.fact_cuestionario fc
                    JOIN glympho_dw.dim_tiempo dt ON dt.tiempo_key = fc.tiempo_key
                    JOIN glympho_dw.dim_participante dp ON dp.participante_key = fc.participante_key
                    JOIN glympho_dw.dim_carrera dc ON dc.carrera_key = fc.carrera_key
                    JOIN glympho_dw.dim_habito dh ON dh.habito_key = fc.habito_key
                    {where_sql}
                    ORDER BY fc.participante_key, dt.fecha DESC
                )
                SELECT
                    facultad,
                    carrera,
                    SUM(CASE WHEN clasificacion_psqi = 'Buen dormidor' THEN 1 ELSE 0 END) AS buenos,
                    SUM(CASE WHEN clasificacion_psqi = 'Mal dormidor' THEN 1 ELSE 0 END) AS malos,
                    COUNT(*) AS total
                FROM ultimo_psqi
                GROUP BY facultad, carrera
                ORDER BY facultad, total DESC, carrera
                """,
                params,
            )
            raw = cur.fetchall()
            rows: List[Dict[str, Any]] = []
            by_fac: Dict[str, List[Dict[str, Any]]] = {}
            for r in raw:
                by_fac.setdefault(r["facultad"], []).append(r)

            tot_b, tot_m, tot_n = 0, 0, 0
            for fac, items in by_fac.items():
                rows.append({"type": "group", "label": fac, "values": [], "bad": []})
                fb, fm, fn = 0, 0, 0
                for it in items:
                    b, m, n = int(it["buenos"]), int(it["malos"]), int(it["total"])
                    pct = round(m / n * 100.0, 1) if n else 0.0
                    rows.append({"type": "item", "label": it["carrera"], "values": [b, m, n, pct], "bad": [False, False, False, pct > 50.0]})
                    fb += b; fm += m; fn += n
                fpct = round(fm / fn * 100.0, 1) if fn else 0.0
                rows.append({"type": "subtotal", "label": f"Total {fac}", "values": [fb, fm, fn, fpct], "bad": [False, False, False, fpct > 50.0]})
                tot_b += fb; tot_m += fm; tot_n += fn

            tpct = round(tot_m / tot_n * 100.0, 1) if tot_n else 0.0
            rows.append({"type": "total", "label": "Totales de cohorte", "values": [tot_b, tot_m, tot_n, tpct], "bad": [False, False, False, False]})

            return {
                "id": "cohorte",
                "title": "RESUMEN DE COHORTE. Buenos y malos dormidores",
                "subtitle": "Clasificación clínica según último PSQI del período por Facultad y Carrera",
                "unit": "Participantes",
                "group_header": "Clasificación (PSQI)",
                "group_start": 0,
                "group_span": 2,
                "columns": ["Buen dormidor (PSQI <= 5)", "Mal dormidor (PSQI > 5)", "Total", "% mal dormidores"],
                "decimals": [0, 0, 0, 1],
                "rows": rows,
                "n_sample": tot_n,
                "note": "RR-03. Hecho: fact_cuestionario (último PSQI del período por participante) · Dimensiones: dim_carrera, dim_tiempo. Cálculo: conteo de participantes; mal dormidor si PSQI global > 5.",
            }

        if report_type == "dias_semana":
            cur.execute(
                f"""
                SELECT
                    dt.es_fin_semana,
                    dt.dia_semana_num,
                    dt.dia_semana,
                    COUNT(*) AS noches,
                    AVG(fsn.sol_min) AS sol,
                    AVG(fsn.waso_min) AS waso,
                    AVG(fsn.tst_min) AS tst,
                    AVG(fsn.min_n3) AS min_n3,
                    AVG(fsn.despertares) AS desp
                FROM glympho_dw.fact_sueno_noche fsn
                JOIN glympho_dw.dim_tiempo dt ON dt.tiempo_key = fsn.tiempo_key
                JOIN glympho_dw.dim_participante dp ON dp.participante_key = fsn.participante_key
                JOIN glympho_dw.dim_carrera dc ON dc.carrera_key = fsn.carrera_key
                JOIN glympho_dw.dim_habito dh ON dh.habito_key = fsn.habito_key
                {where_sql}
                GROUP BY dt.es_fin_semana, dt.dia_semana_num, dt.dia_semana
                ORDER BY dt.es_fin_semana, dt.dia_semana_num
                """,
                params,
            )
            raw = cur.fetchall()
            rows = []
            groups = [
                ("Entre semana", [r for r in raw if not r["es_fin_semana"]]),
                ("Fin de semana", [r for r in raw if r["es_fin_semana"]]),
            ]
            tot_n = 0
            acc_sol = acc_waso = acc_tst = acc_n3 = acc_desp = 0.0
            for gname, items in groups:
                if not items:
                    continue
                rows.append({"type": "group", "label": gname, "values": [], "bad": []})
                gn = 0
                g_sol = g_waso = g_tst = g_n3 = g_desp = 0.0
                for it in items:
                    n = int(it["noches"])
                    sol, waso, tst, n3, desp = float(it["sol"]), float(it["waso"]), float(it["tst"]), float(it["min_n3"]), float(it["desp"])
                    rows.append(_calc_night_row(it["dia_semana"], "item", n, sol, waso, tst, n3, desp))
                    gn += n
                    g_sol += sol * n; g_waso += waso * n; g_tst += tst * n; g_n3 += n3 * n; g_desp += desp * n
                if gn > 0:
                    rows.append(_calc_night_row(f"Total {gname.lower()}", "subtotal", gn, g_sol / gn, g_waso / gn, g_tst / gn, g_n3 / gn, g_desp / gn))
                    tot_n += gn
                    acc_sol += g_sol; acc_waso += g_waso; acc_tst += g_tst; acc_n3 += g_n3; acc_desp += g_desp

            if tot_n > 0:
                trow = _calc_night_row("Totales ponderados", "total", tot_n, acc_sol / tot_n, acc_waso / tot_n, acc_tst / tot_n, acc_n3 / tot_n, acc_desp / tot_n)
                trow["bad"] = [False] * 7
                rows.append(trow)

            return {
                "id": "dias_semana",
                "title": "INDICADORES DE SUEÑO POR DÍA DE LA SEMANA",
                "subtitle": "Comparativa ponderada entre días académicos (lun–vie) y fin de semana (sáb–dom)",
                "unit": "Promedio por noche",
                "group_header": "Promedio por noche",
                "group_start": 1,
                "group_span": 6,
                "columns": ["Noches registradas", "SOL (min)", "WASO (min)", "TST (min)", "SE (%)", "%N3", "Despertares"],
                "decimals": [0, 1, 1, 1, 1, 1, 1],
                "rows": rows,
                "n_sample": tot_n,
                "note": "Hecho: fact_sueno_noche · Dimensión: dim_tiempo. Subtotales y totales ponderados por noches registradas; SE = TST / (SOL + WASO + TST); %N3 = N3 / TST. En rojo: fuera de umbral (SOL > 20, WASO > 40, TST < 420 min, SE < 85%).",
            }

        # Reporte 3: habitos (RR-06)
        cur.execute(
            f"""
            WITH ultimo_psqi AS (
                SELECT DISTINCT ON (fc.participante_key)
                    fc.participante_key,
                    fc.psqi_global
                FROM glympho_dw.fact_cuestionario fc
                JOIN glympho_dw.dim_tiempo dt ON dt.tiempo_key = fc.tiempo_key
                JOIN glympho_dw.dim_participante dp ON dp.participante_key = fc.participante_key
                JOIN glympho_dw.dim_carrera dc ON dc.carrera_key = fc.carrera_key
                JOIN glympho_dw.dim_habito dh ON dh.habito_key = fc.habito_key
                {where_sql}
                ORDER BY fc.participante_key, dt.fecha DESC
            ),
            part_noches AS (
                SELECT
                    fsn.participante_key,
                    AVG(fsn.sol_min) AS sol,
                    AVG(fsn.waso_min) AS waso,
                    AVG(fsn.tst_min) AS tst,
                    AVG(fsn.min_n3) AS min_n3,
                    (ARRAY_AGG(dh.uso_pantallas ORDER BY dt.fecha DESC))[1] AS uso_pantallas,
                    (ARRAY_AGG(dh.cafeina ORDER BY dt.fecha DESC))[1] AS cafeina,
                    (ARRAY_AGG(dh.ejercicio ORDER BY dt.fecha DESC))[1] AS ejercicio,
                    (ARRAY_AGG(dh.estres ORDER BY dt.fecha DESC))[1] AS estres
                FROM glympho_dw.fact_sueno_noche fsn
                JOIN glympho_dw.dim_tiempo dt ON dt.tiempo_key = fsn.tiempo_key
                JOIN glympho_dw.dim_participante dp ON dp.participante_key = fsn.participante_key
                JOIN glympho_dw.dim_carrera dc ON dc.carrera_key = fsn.carrera_key
                JOIN glympho_dw.dim_habito dh ON dh.habito_key = fsn.habito_key
                {where_sql}
                GROUP BY fsn.participante_key
            )
            SELECT
                pn.uso_pantallas, pn.cafeina, pn.ejercicio, pn.estres,
                pn.sol, pn.waso, pn.tst, pn.min_n3,
                up.psqi_global
            FROM part_noches pn
            JOIN ultimo_psqi up ON up.participante_key = pn.participante_key
            """,
            params + params,
        )
        parts = cur.fetchall()
        habit_groups = [
            ("Uso de pantallas antes de dormir", "uso_pantallas", [(">1h", "Sí (> 1 h)"), ("<=1h", "No (<= 1 h)")]),
            ("Cafeína", "cafeina", [("despues_14h", "Después de las 14:00 h"), ("antes_14h_o_ninguna", "Antes de las 14:00 h o ninguna")]),
            ("Ejercicio físico", "ejercicio", [(">=3_dias", ">= 3 días por semana"), ("<3_dias", "< 3 días por semana")]),
            ("Nivel de estrés académico", "estres", [("alto", "Alto"), ("medio", "Medio"), ("bajo", "Bajo")]),
        ]

        rows = []
        n_total = len(parts)
        for gtitle, key, levels in habit_groups:
            rows.append({"type": "group", "label": gtitle, "values": [], "bad": []})
            cn = 0
            c_sol = c_waso = c_tst = c_n3 = c_psqi = 0.0
            for raw_val, display_val in levels:
                sub = [p for p in parts if p[key] == raw_val]
                if not sub:
                    continue
                n = len(sub)
                sol = sum(float(p["sol"]) for p in sub) / n
                waso = sum(float(p["waso"]) for p in sub) / n
                tst = sum(float(p["tst"]) for p in sub) / n
                n3 = sum(float(p["min_n3"]) for p in sub) / n
                psqi = sum(float(p["psqi_global"]) for p in sub) / n
                tib = sol + waso + tst
                se = (tst / tib * 100.0) if tib else 0.0
                pct_n3 = (n3 / tst * 100.0) if tst else 0.0
                rows.append({
                    "type": "item",
                    "label": display_val,
                    "values": [n, round(sol, 1), round(waso, 1), round(tst, 1), round(se, 1), round(pct_n3, 1), round(psqi, 1)],
                    "bad": [False, sol > 20.0, waso > 40.0, tst < 420.0, se < 85.0, False, psqi > 5.0],
                })
                cn += n
                c_sol += sol * n; c_waso += waso * n; c_tst += tst * n; c_n3 += n3 * n; c_psqi += psqi * n

            if cn > 0:
                msol, mwaso, mtst, mn3, mpsqi = c_sol / cn, c_waso / cn, c_tst / cn, c_n3 / cn, c_psqi / cn
                mse = mtst / (msol + mwaso + mtst) * 100.0
                mpn3 = mn3 / mtst * 100.0
                rows.append({
                    "type": "subtotal",
                    "label": "Cohorte ponderada",
                    "values": [cn, round(msol, 1), round(mwaso, 1), round(mtst, 1), round(mse, 1), round(mpn3, 1), round(mpsqi, 1)],
                    "bad": [False] * 7,
                })

        return {
            "id": "habitos",
            "title": "HÁBITOS DE HIGIENE VS. INDICADORES DE SUEÑO",
            "subtitle": "Comparativa de indicadores objetivos y PSQI por nivel de hábito reportado",
            "unit": "Promedio por participante",
            "group_header": "Promedio del período",
            "group_start": 1,
            "group_span": 6,
            "columns": ["Participantes", "SOL (min)", "WASO (min)", "TST (min)", "SE (%)", "%N3", "PSQI global"],
            "decimals": [0, 1, 1, 1, 1, 1, 1],
            "rows": rows,
            "n_sample": n_total,
            "note": "RR-06. Hechos: fact_sueno_noche y fact_cuestionario · Dimensión: dim_habito. Comparación descriptiva entre grupos (no implica causalidad directa). En rojo: fuera de umbral (SOL > 20, WASO > 40, TST < 420 min, SE < 85%, PSQI > 5).",
        }
