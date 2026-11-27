"""Validadores de calidad de datos para el proceso ETL (RETL-02)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Tuple


REQUIRED_CSV_COLUMNS = [
    "fecha",
    "tib_min",
    "tst_min",
    "sol_min",
    "despertares",
    "min_n1",
    "min_n2",
    "min_n3",
    "min_rem",
]


def validate_sleep_night_row(row: Dict[str, Any], row_index: int) -> Tuple[bool, Dict[str, Any] | None, str | None]:
    """
    Valida coherencia fisiologica y de rangos para una noche de sueno (RETL-02):
    - Fecha ISO valida (YYYY-MM-DD)
    - Valores numericos no negativos
    - 0 < TST <= 1440, 0 < TIB <= 1440
    - TST + SOL <= TIB (WASO >= 0)
    - |N1 + N2 + N3 + REM - TST| <= 1.0 min
    """
    try:
        raw_fecha = str(row.get("fecha", "")).strip()
        if not raw_fecha:
            return False, None, f"Fila {row_index}: falta 'fecha'."
        parsed_fecha = datetime.strptime(raw_fecha[:10], "%Y-%m-%d").date()
        if parsed_fecha > date.today():
            return False, None, f"Fila {row_index}: fecha futura no permitida ({raw_fecha})."

        tib = float(row["tib_min"])
        tst = float(row["tst_min"])
        sol = float(row["sol_min"])
        despertares = int(float(row["despertares"]))
        n1 = float(row["min_n1"])
        n2 = float(row["min_n2"])
        n3 = float(row["min_n3"])
        rem = float(row["min_rem"])
    except (KeyError, TypeError, ValueError) as exc:
        return False, None, f"Fila {row_index}: error de formato o columna faltante ({exc})."

    if any(v < 0 for v in (tib, tst, sol, despertares, n1, n2, n3, rem)):
        return False, None, f"Fila {row_index}: valores negativos no permitidos."

    if tib <= 0 or tib > 1440 or tst <= 0 or tst > 1440:
        return False, None, f"Fila {row_index}: TIB ({tib}) o TST ({tst}) fuera de rango (1..1440 min)."

    if sol > 360:
        return False, None, f"Fila {row_index}: latencia SOL ({sol} min) excede maximo razonable (360 min)."

    if despertares > 50:
        return False, None, f"Fila {row_index}: numero de despertares ({despertares}) fuera de rango."

    if tst + sol > tib + 0.01:
        return (
            False,
            None,
            f"Fila {row_index}: incoherencia TST+SOL ({tst+sol:.1f}) > TIB ({tib:.1f}).",
        )

    sum_stages = n1 + n2 + n3 + rem
    if abs(sum_stages - tst) > 1.0:
        return (
            False,
            None,
            f"Fila {row_index}: suma de fases N1+N2+N3+REM ({sum_stages:.1f}) difiere de TST ({tst:.1f}).",
        )

    clean = {
        "fecha": parsed_fecha,
        "tib_min": round(tib, 2),
        "tst_min": round(tst, 2),
        "sol_min": round(sol, 2),
        "despertares": despertares,
        "min_n1": round(n1, 2),
        "min_n2": round(n2, 2),
        "min_n3": round(n3, 2),
        "min_rem": round(rem, 2),
    }
    if "codigo_participante" in row and str(row["codigo_participante"]).strip():
        clean["codigo_participante"] = str(row["codigo_participante"]).strip()
    return True, clean, None


def validate_csv_records(rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Valida lote de filas de CSV deduplicando por fecha (y codigo si viene)."""
    valid: List[Dict[str, Any]] = []
    errors: List[str] = []
    seen_keys = set()

    for idx, row in enumerate(rows, start=2):  # fila 1 = encabezado
        ok, clean, err = validate_sleep_night_row(row, idx)
        if not ok or clean is None:
            if err:
                errors.append(err)
            continue
        dedup_key = (clean.get("codigo_participante", ""), clean["fecha"])
        if dedup_key in seen_keys:
            errors.append(f"Fila {idx}: fecha duplicada ({clean['fecha']}) ignorada.")
            continue
        seen_keys.add(dedup_key)
        valid.append(clean)

    return valid, errors
