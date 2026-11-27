"""Algoritmos clinicos validados para PSQI (Buysse et al., 1989), ESS y KPIs objetivos."""

from __future__ import annotations

from datetime import time
from typing import Dict


def parse_time(val: str | time) -> time:
    if isinstance(val, time):
        return val
    parts = str(val).strip().split(":")
    return time(int(parts[0]), int(parts[1]))


def compute_hours_in_bed(bedtime: str | time, waketime: str | time) -> float:
    """Calcula horas en cama manejando cruce de medianoche (ej. 23:30 -> 06:30 = 7.0 h)."""
    bt = parse_time(bedtime)
    wt = parse_time(waketime)
    bt_min = bt.hour * 60 + bt.minute
    wt_min = wt.hour * 60 + wt.minute
    diff_min = wt_min - bt_min
    if diff_min <= 0:
        diff_min += 24 * 60
    return round(diff_min / 60.0, 4)


def _recode_sum_0_to_6(total: int) -> int:
    if total == 0:
        return 0
    if total <= 2:
        return 1
    if total <= 4:
        return 2
    return 3


def compute_psqi(
    hora_acostarse: str | time,
    minutos_latencia: int,
    hora_levantarse: str | time,
    horas_sueno_real: float,
    items: Dict[str, int],
) -> Dict[str, object]:
    """
    Calcula los 7 componentes (C1-C7) y el puntaje global PSQI (0-21) segun Buysse et al. (1989).
    items debe contener: '5a'..'5j', '6', '7', '8', '9' con valores enteros 0..3.
    """
    required = ["5a", "5b", "5c", "5d", "5e", "5f", "5g", "5h", "5i", "5j", "6", "7", "8", "9"]
    for key in required:
        if key not in items:
            raise ValueError(f"Falta el item PSQI '{key}'")
        val = int(items[key])
        if val < 0 or val > 3:
            raise ValueError(f"Item PSQI '{key}' fuera de rango (0-3): {val}")

    # C1: Calidad subjetiva del sueno (item 6 directo)
    c1 = int(items["6"])

    # C2: Latencia del sueno (minutos_latencia recodificado + item 5a)
    if minutos_latencia <= 15:
        lat_score = 0
    elif minutos_latencia <= 30:
        lat_score = 1
    elif minutos_latencia <= 60:
        lat_score = 2
    else:
        lat_score = 3
    c2 = _recode_sum_0_to_6(lat_score + int(items["5a"]))

    # C3: Duracion del sueno (>7h=0, 6-7h=1, 5-6h=2, <5h=3)
    if horas_sueno_real > 7.0:
        c3 = 0
    elif horas_sueno_real >= 6.0:
        c3 = 1
    elif horas_sueno_real >= 5.0:
        c3 = 2
    else:
        c3 = 3

    # C4: Eficiencia habitual del sueno
    tib_hours = compute_hours_in_bed(hora_acostarse, hora_levantarse)
    eff_pct = (horas_sueno_real / tib_hours) * 100.0 if tib_hours > 0 else 0.0
    if eff_pct >= 85.0:
        c4 = 0
    elif eff_pct >= 75.0:
        c4 = 1
    elif eff_pct >= 65.0:
        c4 = 2
    else:
        c4 = 3

    # C5: Alteraciones del sueno (suma 5b..5j)
    c5_sum = sum(int(items[f"5{ch}"]) for ch in "bcdefghij")
    if c5_sum == 0:
        c5 = 0
    elif c5_sum <= 9:
        c5 = 1
    elif c5_sum <= 18:
        c5 = 2
    else:
        c5 = 3

    # C6: Uso de medicacion para dormir (item 7 directo)
    c6 = int(items["7"])

    # C7: Disfuncion diurna (items 8 + 9)
    c7 = _recode_sum_0_to_6(int(items["8"]) + int(items["9"]))

    psqi_global = c1 + c2 + c3 + c4 + c5 + c6 + c7
    clasificacion = "Buen dormidor" if psqi_global <= 5 else "Mal dormidor"

    return {
        "c1_calidad": c1,
        "c2_latencia": c2,
        "c3_duracion": c3,
        "c4_eficiencia": c4,
        "c5_alteraciones": c5,
        "c6_medicacion": c6,
        "c7_disfuncion": c7,
        "psqi_global": psqi_global,
        "clasificacion_psqi": clasificacion,
        "eficiencia_habitual_pct": round(eff_pct, 2),
        "horas_en_cama": tib_hours,
    }


def compute_ess(situaciones: Dict[int, int] | list[int]) -> Dict[str, object]:
    """Calcula Escala de Somnolencia de Epworth (0-24) y su categoria clinica."""
    if isinstance(situaciones, list):
        vals = [int(v) for v in situaciones]
    else:
        vals = [int(situaciones[i]) for i in range(1, 9)]

    if len(vals) != 8 or any(v < 0 or v > 3 for v in vals):
        raise ValueError("ESS requiere exactamente 8 situaciones con valores entre 0 y 3.")

    total = sum(vals)
    if total <= 10:
        clasif = "Normal"
    elif total <= 14:
        clasif = "Somnolencia leve"
    elif total <= 17:
        clasif = "Somnolencia moderada"
    else:
        clasif = "Somnolencia severa"

    return {"ess_total": total, "clasificacion_ess": clasif}


def compute_objective_kpis(
    tib_min: float,
    tst_min: float,
    sol_min: float,
    min_n3: float,
) -> Dict[str, float]:
    """Calcula WASO, SE (%), %N3 e Indice de Oportunidad Glinfatica (metrica derivada)."""
    if tib_min <= 0 or tst_min <= 0:
        raise ValueError("TIB y TST deben ser positivos.")
    waso_min = round(max(0.0, tib_min - sol_min - tst_min), 2)
    se_pct = round((tst_min / tib_min) * 100.0, 2)
    pct_n3 = round((min_n3 / tst_min) * 100.0, 2)
    # Metrica derivada complementaria (IG, escala 0.000 - 1.000)
    ig_raw = (pct_n3 / 25.0) * (se_pct / 100.0) * min(1.0, 20.0 / max(sol_min, 10.0))
    indice_glinfatico = round(max(0.0, min(1.0, ig_raw)), 3)
    return {
        "waso_min": waso_min,
        "se_pct": se_pct,
        "pct_n3": pct_n3,
        "indice_glinfatico": indice_glinfatico,
    }
