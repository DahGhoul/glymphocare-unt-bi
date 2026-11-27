"""Servicio estadistico real (correlaciones Pearson, regresion lineal y comparacion entre grupos)."""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
from scipy import stats


def linear_regression_summary(xs: List[float], ys: List[float]) -> Dict[str, float | None]:
    if len(xs) < 3 or len(ys) < 3 or np.std(xs) == 0 or np.std(ys) == 0:
        return {"slope": None, "intercept": None, "r": None, "r2": None, "p_value": None}
    res = stats.linregress(xs, ys)
    return {
        "slope": round(float(res.slope), 4),
        "intercept": round(float(res.intercept), 4),
        "r": round(float(res.rvalue), 3),
        "r2": round(float(res.rvalue ** 2), 3),
        "p_value": round(float(res.pvalue), 5),
    }


def _safe_pearson(x: List[float], y: List[float]) -> Dict[str, float | None]:
    if len(x) < 4 or np.std(x) == 0 or np.std(y) == 0:
        return {"r": None, "p_value": None}
    r, p = stats.pearsonr(x, y)
    return {"r": round(float(r), 3), "p_value": round(float(p), 5)}


def compute_habit_correlations_and_findings(participant_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calcula matriz de correlacion real (habitos codificados vs KPIs) y hallazgos automaticos (RF-07)
    mediante pruebas t de Welch / diferencias reales de medias sobre los participantes filtrados.
    """
    if len(participant_rows) < 4:
        return {"matrix": {"habits": [], "kpis": [], "cells": []}, "findings": []}

    # Codificacion ordinal de habitos (mayor valor = habito mas protector o mayor exposicion segun etiqueta)
    habit_specs = [
        ("uso_pantallas", "Pantallas (>1h)", lambda r: 1.0 if r["uso_pantallas"] == ">1h" else 0.0),
        ("cafeina", "Cafeina (>14h)", lambda r: 1.0 if r["cafeina"] == "despues_14h" else 0.0),
        ("ejercicio", "Ejercicio (>=3d)", lambda r: 1.0 if r["ejercicio"] == ">=3_dias" else 0.0),
        ("estres", "Estres (nivel)", lambda r: {"bajo": 0.0, "medio": 1.0, "alto": 2.0}.get(r["estres"], 1.0)),
        ("regularidad", "Horario irregular", lambda r: 1.0 if r["regularidad_horarios"] == "irregular" else 0.0),
    ]
    kpi_specs = [
        ("psqi_global", "PSQI global"),
        ("ess_total", "ESS"),
        ("sol_min", "SOL (min)"),
        ("waso_min", "WASO (min)"),
        ("se_pct", "SE (%)"),
        ("pct_n3", "%N3"),
    ]

    cells = []
    for h_idx, (_, h_label, h_fn) in enumerate(habit_specs):
        x = [h_fn(r) for r in participant_rows]
        for k_idx, (k_col, k_label) in enumerate(kpi_specs):
            y = [float(r[k_col]) for r in participant_rows]
            stat = _safe_pearson(x, y)
            cells.append({
                "habit_index": h_idx,
                "kpi_index": k_idx,
                "habit": h_label,
                "kpi": k_label,
                "r": stat["r"],
                "p_value": stat["p_value"],
            })

    findings: List[Dict[str, Any]] = []

    def add_group_finding(
        title: str,
        field: str,
        pos_val: str,
        neg_val: str,
        metric: str,
        unit: str,
        pos_label: str,
        neg_label: str,
    ) -> None:
        g_pos = [float(r[metric]) for r in participant_rows if r[field] == pos_val]
        g_neg = [float(r[metric]) for r in participant_rows if r[field] == neg_val]
        if len(g_pos) < 3 or len(g_neg) < 3:
            return
        m_pos = float(np.mean(g_pos))
        m_neg = float(np.mean(g_neg))
        diff = m_pos - m_neg
        _, p_val = stats.ttest_ind(g_pos, g_neg, equal_var=False)
        sign = "+" if diff >= 0 else ""
        findings.append({
            "titulo": title,
            "descripcion": (
                f"Los participantes con {pos_label} (n={len(g_pos)}) presentan un promedio de "
                f"{m_pos:.1f} {unit} frente a {m_neg:.1f} {unit} en quienes reportan {neg_label} "
                f"(n={len(g_neg)}): diferencia de {sign}{diff:.1f} {unit}."
            ),
            "diferencia": round(diff, 2),
            "unidad": unit,
            "p_value": round(float(p_val), 4),
            "significativo": bool(p_val < 0.05),
        })

    add_group_finding(
        "Pantallas nocturnas y latencia de sueno (SOL)",
        "uso_pantallas", ">1h", "<=1h", "sol_min", "min",
        "uso de pantallas > 1 h antes de dormir", "uso <= 1 h",
    )
    add_group_finding(
        "Cafeina vespertina y calidad subjetiva (PSQI)",
        "cafeina", "despues_14h", "antes_14h_o_ninguna", "psqi_global", "pts",
        "consumo de cafeina despues de las 14:00 h", "consumo antes de las 14 h o ninguno",
    )
    add_group_finding(
        "Actividad fisica y sueno profundo (%N3)",
        "ejercicio", ">=3_dias", "<3_dias", "pct_n3", "%",
        "ejercicio >= 3 dias/semana", "ejercicio < 3 dias/semana",
    )
    add_group_finding(
        "Estres academico alto y fragmentacion (WASO)",
        "estres", "alto", "bajo", "waso_min", "min",
        "nivel de estres alto", "nivel de estres bajo",
    )

    return {
        "matrix": {
            "habits": [h[1] for h in habit_specs],
            "kpis": [k[1] for k in kpi_specs],
            "cells": cells,
        },
        "findings": findings,
    }


def boxplot_stats(values: List[float]) -> List[float]:
    """Retorna [min, q1, median, q3, max] para ECharts boxplot."""
    if not values:
        return [0.0, 0.0, 0.0, 0.0, 0.0]
    arr = np.array(values, dtype=float)
    q1, med, q3 = np.percentile(arr, [25, 50, 75])
    return [
        round(float(np.min(arr)), 2),
        round(float(q1), 2),
        round(float(med), 2),
        round(float(q3), 2),
        round(float(np.max(arr)), 2),
    ]
