"""Motor de evaluacion de reglas y umbrales configurables en base de datos (RF-08, RNF-06)."""

from __future__ import annotations

import operator
from typing import Any, Dict, List

OPS = {
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
}


def evaluate_rules(kpis: Dict[str, float | None], rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Evalua los KPIs de un participante o cohorte contra las reglas activas de recomendacion_regla."""
    triggered: List[Dict[str, Any]] = []
    for r in rules:
        if not r.get("activo", True):
            continue
        code = r["kpi_codigo"]
        val = kpis.get(code)
        if val is None:
            continue
        op_fn = OPS.get(r["operador"])
        if not op_fn:
            continue
        umbral = float(r["umbral"])
        if op_fn(float(val), umbral):
            triggered.append(
                {
                    "rule_id": r["id"],
                    "kpi_codigo": code,
                    "valor_actual": round(float(val), 2),
                    "operador": r["operador"],
                    "umbral": umbral,
                    "severidad": r["severidad"],
                    "titulo": r["titulo"],
                    "texto_recomendacion": r["texto_recomendacion"],
                }
            )
    sev_order = {"critico": 0, "alerta": 1, "info": 2}
    triggered.sort(key=lambda x: sev_order.get(x["severidad"], 9))
    return triggered
