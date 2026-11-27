"""Tests unitarios y de integracion para el calculo PSQI/ESS/KPIs y ETL."""

import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from etl.psqi_calculator import (
    compute_ess,
    compute_hours_in_bed,
    compute_objective_kpis,
    compute_psqi,
)
from etl.validators import validate_csv_records


def test_hours_in_bed_midnight_wrap():
    assert compute_hours_in_bed("23:30", "06:30") == 7.0
    assert compute_hours_in_bed("00:15", "07:15") == 7.0
    assert compute_hours_in_bed("22:00", "06:30") == 8.5


def test_psqi_good_sleeper():
    items = {k: 0 for k in ["5a","5b","5c","5d","5e","5f","5g","5h","5i","5j","6","7","8","9"]}
    items["5b"] = 1
    items["6"] = 1
    res = compute_psqi("23:00", 12, "07:00", 7.5, items)
    assert res["c1_calidad"] == 1
    assert res["c2_latencia"] == 0
    assert res["c3_duracion"] == 0
    assert res["c4_eficiencia"] == 0  # 7.5/8 = 93.75% >= 85%
    assert res["c5_alteraciones"] == 1
    assert res["c6_medicacion"] == 0
    assert res["c7_disfuncion"] == 0
    assert res["psqi_global"] == 2
    assert res["clasificacion_psqi"] == "Buen dormidor"


def test_psqi_bad_sleeper_edge_cases():
    items = {
        "5a": 3, "5b": 3, "5c": 2, "5d": 2, "5e": 1, "5f": 1, "5g": 2, "5h": 1, "5i": 2, "5j": 1,
        "6": 3, "7": 2, "8": 2, "9": 2,
    }
    res = compute_psqi("23:30", 65, "06:30", 4.5, items)
    assert res["c1_calidad"] == 3
    assert res["c2_latencia"] == 3  # 3 (lat>60) + 3 (5a=3) = 6 -> 3
    assert res["c3_duracion"] == 3  # <5h -> 3
    assert res["c4_eficiencia"] == 3  # 4.5/7 = 64.29% < 65% -> 3
    assert res["c5_alteraciones"] == 2  # sum=15 -> 2
    assert res["c6_medicacion"] == 2
    assert res["c7_disfuncion"] == 2  # 2+2=4 -> 2
    assert res["psqi_global"] == 18
    assert res["clasificacion_psqi"] == "Mal dormidor"


def test_ess_classifications():
    assert compute_ess([1, 1, 1, 0, 1, 0, 1, 1]) == {"ess_total": 6, "clasificacion_ess": "Normal"}
    assert compute_ess([2, 2, 2, 1, 2, 1, 1, 1]) == {"ess_total": 12, "clasificacion_ess": "Somnolencia leve"}
    assert compute_ess([3, 3, 2, 2, 2, 2, 2, 2]) == {"ess_total": 18, "clasificacion_ess": "Somnolencia severa"}


def test_objective_kpis():
    kpis = compute_objective_kpis(tib_min=480, tst_min=408, sol_min=20, min_n3=81.6)
    assert kpis["waso_min"] == 52.0
    assert kpis["se_pct"] == 85.0
    assert kpis["pct_n3"] == 20.0
    assert 0.0 < kpis["indice_glinfatico"] <= 1.0


def test_csv_validator_rejects_inconsistent_and_duplicates():
    rows = [
        {"fecha": "2026-11-20", "tib_min": 480, "tst_min": 420, "sol_min": 15, "despertares": 1, "min_n1": 25, "min_n2": 215, "min_n3": 90, "min_rem": 90},
        {"fecha": "2026-11-20", "tib_min": 480, "tst_min": 420, "sol_min": 15, "despertares": 1, "min_n1": 25, "min_n2": 215, "min_n3": 90, "min_rem": 90},  # duplicada
        {"fecha": "2026-11-21", "tib_min": 400, "tst_min": 410, "sol_min": 15, "despertares": 1, "min_n1": 25, "min_n2": 215, "min_n3": 85, "min_rem": 85},  # TST+SOL > TIB
        {"fecha": "2026-11-22", "tib_min": 480, "tst_min": 420, "sol_min": 15, "despertares": 1, "min_n1": 10, "min_n2": 100, "min_n3": 50, "min_rem": 50},   # suma fases != TST
    ]
    valid, errors = validate_csv_records(rows)
    assert len(valid) == 1
    assert len(errors) == 3
