"""
Generador determinista de cohorte universitaria UNT realista (90 participantes,
~2,250 noches registradas y evaluaciones longitudinales PSQI/ESS Sep-Nov 2026) +
3 archivos CSV de wearables de demostracion listos para carga en vivo.
"""

from __future__ import annotations

import csv
import os
import random
import sys
from datetime import date, time, timedelta
from pathlib import Path

import bcrypt
import psycopg
from psycopg.rows import dict_row

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from etl.run_etl import get_dsn, run_etl

CARRERAS = [
    ("Ingeniería", "Ing. de Sistemas", 22),
    ("Ingeniería", "Ing. Industrial", 16),
    ("Ingeniería", "Ing. Civil", 12),
    ("Ciencias Económicas", "Administración", 15),
    ("Ciencias Económicas", "Contabilidad", 12),
    ("Ciencias de la Salud", "Psicología", 8),
    ("Ciencias de la Salud", "Enfermería", 5),
]  # Total = 90 estudiantes UNT

DEMO_USERS = [
    ("admin@glymphocare.edu.pe", "Glympho2026!", "Dr. Admin BI (UNT)", "admin"),
    ("analista@glymphocare.edu.pe", "Glympho2026!", "Analista G5", "analista"),
    ("investigador@glymphocare.edu.pe", "Glympho2026!", "Investigador Campo", "investigador"),
    ("estudiante@glymphocare.edu.pe", "Glympho2026!", "Diego Cuba (Participante)", "participante"),
]


def _hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode("utf-8")


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def seed_database(dsn: str | None = None) -> None:
    rng = random.Random(2026)
    conn_dsn = (dsn or get_dsn()).replace("postgresql+psycopg://", "postgresql://")

    with psycopg.connect(conn_dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            # Verificar si ya existe cohorte
            cur.execute("SELECT COUNT(*) AS c FROM glympho_oltp.participante")
            existing = cur.fetchone()["c"]
            if existing >= 90:
                print(f"Cohorte ya sembrada ({existing} participantes). Ejecutando ETL...")
                conn.commit()
                run_etl(origen="seed_check", dsn=conn_dsn)
                return

            # 1. Usuarios demo
            pw_hash = _hash_pw("Glympho2026!")
            user_ids = {}
            for email, _, nombre, rol in DEMO_USERS:
                cur.execute(
                    """
                    INSERT INTO glympho_oltp.usuario (email, password_hash, nombre_display, rol, activo)
                    VALUES (%s, %s, %s, %s, TRUE)
                    ON CONFLICT (email) DO UPDATE SET nombre_display = EXCLUDED.nombre_display
                    RETURNING id
                    """,
                    (email, pw_hash, nombre, rol),
                )
                user_ids[email] = cur.fetchone()["id"]

            # 2. 90 Participantes UNT
            idx_global = 0
            eval_dates = [date(2026, 9, 15), date(2026, 10, 15), date(2026, 11, 15)]
            base_night = date(2026, 10, 26)  # 30 noches hasta 2026-11-24

            for facultad, carrera, count in CARRERAS:
                for _ in range(count):
                    idx_global += 1
                    codigo = f"UNT-{idx_global:03d}"
                    uid = user_ids["estudiante@glymphocare.edu.pe"] if idx_global == 1 else None
                    edad = rng.randint(18, 26)
                    sexo = rng.choice(["F", "M"]) if rng.random() < 0.96 else "Otro"
                    ciclo = rng.randint(2, 10)
                    reg_date = date(2026, 9, rng.randint(1, 12))

                    cur.execute(
                        """
                        INSERT INTO glympho_oltp.participante
                            (usuario_id, codigo, edad, sexo, facultad, carrera, ciclo, fecha_registro)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (codigo) DO UPDATE SET ciclo = EXCLUDED.ciclo
                        RETURNING id
                        """,
                        (uid, codigo, edad, sexo, facultad, carrera, ciclo, reg_date),
                    )
                    pid = cur.fetchone()["id"]

                    cur.execute(
                        """
                        INSERT INTO glympho_oltp.consentimiento (participante_id, version_texto, aceptado, fecha)
                        VALUES (%s, 'v1.0-UNT-2026', TRUE, %s)
                        """,
                        (pid, reg_date),
                    )

                    # Perfil de habitos realista por facultad (Ingenieria usa mas pantallas/cafeina)
                    p_pantallas = 0.68 if facultad == "Ingeniería" else (0.58 if facultad == "Ciencias Económicas" else 0.45)
                    pantallas = ">1h" if rng.random() < p_pantallas else "<=1h"
                    cafeina = "despues_14h" if rng.random() < (0.48 if facultad == "Ingeniería" else 0.35) else "antes_14h_o_ninguna"
                    ejercicio = ">=3_dias" if rng.random() < 0.34 else "<3_dias"
                    estres = rng.choices(["alto", "medio", "bajo"], weights=[0.40, 0.40, 0.20])[0]
                    regularidad = "irregular" if (pantallas == ">1h" and rng.random() < 0.65) else ("regular" if rng.random() < 0.6 else "irregular")

                    # Severidad latente fisiologica del estudiante (controla coherencia entre PSQI, ESS y noches)
                    risk_score = (
                        (1.2 if pantallas == ">1h" else -0.5)
                        + (1.0 if cafeina == "despues_14h" else -0.4)
                        + (-1.1 if ejercicio == ">=3_dias" else 0.6)
                        + (1.3 if estres == "alto" else (0.3 if estres == "medio" else -0.9))
                        + (0.7 if regularidad == "irregular" else -0.4)
                        + rng.gauss(0, 0.7)
                    )

                    # Evaluaciones longitudinales (Sep, Oct, Nov) con leve mejora si ejercicio/bajo riesgo
                    num_evals = 3 if idx_global % 3 != 0 else 2
                    for e_idx, edate in enumerate(eval_dates[:num_evals]):
                        # Mejora gradual en cohorte con intervencion de higiene (e_idx)
                        h_pantallas = pantallas
                        if e_idx == 2 and pantallas == ">1h" and rng.random() < 0.22:
                            h_pantallas = "<=1h"

                        cur.execute(
                            """
                            INSERT INTO glympho_oltp.habito_sueno
                                (participante_id, fecha, pantallas_antes_dormir, cafeina_nivel, ejercicio_nivel, estres_nivel, regularidad_horarios)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (participante_id, fecha) DO NOTHING
                            """,
                            (pid, edate, h_pantallas, cafeina, ejercicio, estres, regularidad),
                        )

                        local_risk = risk_score - (0.35 * e_idx if h_pantallas == "<=1h" else 0.0)
                        sol_q = int(_clamp(round(18 + local_risk * 6.5 + rng.gauss(0, 5)), 5, 75))
                        horas_sueno = round(_clamp(7.1 - local_risk * 0.45 + rng.gauss(0, 0.45), 4.3, 8.8), 2)
                        bed_hour = 23 if local_risk < 1.5 else 0
                        bed_min = rng.choice([0, 15, 30, 45])
                        hora_acostarse = time(bed_hour, bed_min)
                        tib_q = horas_sueno + (sol_q / 60.0) + _clamp(0.35 + local_risk * 0.12, 0.1, 1.2)
                        wake_total_min = (bed_hour * 60 + bed_min + int(round(tib_q * 60))) % (24 * 60)
                        hora_levantarse = time(wake_total_min // 60, wake_total_min % 60)

                        cur.execute(
                            """
                            INSERT INTO glympho_oltp.cuestionario_psqi
                                (participante_id, fecha, hora_acostarse, minutos_latencia, hora_levantarse, horas_sueno_real)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (participante_id, fecha) DO NOTHING
                            RETURNING id
                            """,
                            (pid, edate, hora_acostarse, sol_q, hora_levantarse, horas_sueno),
                        )
                        psqi_row = cur.fetchone()
                        if psqi_row:
                            psqi_id = psqi_row["id"]
                            p_sev = _clamp((local_risk + 1.5) / 5.0, 0.05, 0.90)
                            items_psqi = {
                                "5a": int(_clamp(round(p_sev * 2.7 + rng.gauss(0, 0.5)), 0, 3)),
                                "5b": int(_clamp(round(p_sev * 2.1 + rng.gauss(0, 0.6)), 0, 3)),
                                "5c": int(_clamp(round(p_sev * 1.5 + rng.gauss(0, 0.6)), 0, 3)),
                                "5d": int(_clamp(round(p_sev * 0.9 + rng.gauss(0, 0.5)), 0, 3)),
                                "5e": int(_clamp(round(p_sev * 0.8 + rng.gauss(0, 0.5)), 0, 3)),
                                "5f": int(_clamp(round(p_sev * 1.1 + rng.gauss(0, 0.5)), 0, 3)),
                                "5g": int(_clamp(round(p_sev * 1.2 + rng.gauss(0, 0.5)), 0, 3)),
                                "5h": int(_clamp(round(p_sev * 1.0 + rng.gauss(0, 0.5)), 0, 3)),
                                "5i": int(_clamp(round(p_sev * 1.6 + rng.gauss(0, 0.6)), 0, 3)),
                                "5j": int(_clamp(round(p_sev * 0.9 + rng.gauss(0, 0.5)), 0, 3)),
                                "6": int(_clamp(round(p_sev * 2.5 + rng.gauss(0, 0.5)), 0, 3)),
                                "7": 1 if (local_risk > 2.0 and rng.random() < 0.35) else 0,
                                "8": int(_clamp(round(p_sev * 2.0 + rng.gauss(0, 0.5)), 0, 3)),
                                "9": int(_clamp(round(p_sev * 2.1 + rng.gauss(0, 0.5)), 0, 3)),
                            }
                            for ic, iv in items_psqi.items():
                                cur.execute(
                                    """
                                    INSERT INTO glympho_oltp.respuesta_psqi (psqi_id, item_codigo, valor)
                                    VALUES (%s, %s, %s)
                                    """,
                                    (psqi_id, ic, iv),
                                )

                        cur.execute(
                            """
                            INSERT INTO glympho_oltp.cuestionario_ess (participante_id, fecha)
                            VALUES (%s, %s)
                            ON CONFLICT (participante_id, fecha) DO NOTHING
                            RETURNING id
                            """,
                            (pid, edate),
                        )
                        ess_row = cur.fetchone()
                        if ess_row:
                            ess_id = ess_row["id"]
                            p_ess = _clamp((local_risk + 1.8) / 5.2, 0.1, 0.85)
                            for snum in range(1, 9):
                                sval = int(_clamp(round(p_ess * 2.3 + rng.gauss(0, 0.65)), 0, 3))
                                cur.execute(
                                    """
                                    INSERT INTO glympho_oltp.respuesta_ess (ess_id, situacion_num, valor)
                                    VALUES (%s, %s, %s)
                                    """,
                                    (ess_id, snum, sval),
                                )

                    # 25 noches objetivas por estudiante (~2,250 noches en total)
                    n_nights = 25
                    for d_off in range(n_nights):
                        n_date = base_night + timedelta(days=d_off)
                        is_wknd = n_date.isoweekday() >= 6

                        sol = round(_clamp(19.0 + (7.5 if pantallas == ">1h" else -3.0) + (4.5 if cafeina == "despues_14h" else -1.5) + (3.5 if estres == "alto" else -2.0) + (3.0 if is_wknd else 0.0) + rng.gauss(0, 4.0), 6.0, 68.0), 1)
                        waso = round(_clamp(36.0 + (6.0 if cafeina == "despues_14h" else -2.0) + (6.5 if estres == "alto" else -4.0) + (-5.0 if ejercicio == ">=3_dias" else 2.5) + rng.gauss(0, 7.0), 8.0, 95.0), 1)
                        tst = round(_clamp(395.0 + (32.0 if is_wknd else -12.0) + (-14.0 if pantallas == ">1h" else 10.0) + (-16.0 if cafeina == "despues_14h" else 8.0) + (16.0 if ejercicio == ">=3_dias" else -6.0) + (-14.0 if estres == "alto" else 10.0) + rng.gauss(0, 22.0), 260.0, 540.0), 1)
                        tib = round(tst + sol + waso, 1)
                        despertares = int(_clamp(round(1.8 + (waso / 24.0) + rng.gauss(0, 0.7)), 0, 9))

                        pct_n3_target = _clamp(
                            17.8
                            + (3.4 if ejercicio == ">=3_dias" else -1.5)
                            + (-2.6 if pantallas == ">1h" else 1.4)
                            + (-2.2 if cafeina == "despues_14h" else 1.0)
                            + (-2.8 if estres == "alto" else (1.5 if estres == "bajo" else 0.0))
                            + rng.gauss(0, 2.1),
                            8.0,
                            28.0,
                        )
                        pct_rem = _clamp(21.0 + rng.gauss(0, 2.2), 14.0, 28.0)
                        pct_n1 = _clamp(6.0 + rng.gauss(0, 1.3), 3.0, 12.0)

                        min_n3 = round(tst * (pct_n3_target / 100.0), 1)
                        min_rem = round(tst * (pct_rem / 100.0), 1)
                        min_n1 = round(tst * (pct_n1 / 100.0), 1)
                        min_n2 = round(tst - (min_n1 + min_n3 + min_rem), 1)

                        cur.execute(
                            """
                            INSERT INTO glympho_oltp.registro_sueno_noche
                                (participante_id, fecha, tib_min, tst_min, sol_min, despertares,
                                 min_n1, min_n2, min_n3, min_rem, origen)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'seed')
                            ON CONFLICT (participante_id, fecha) DO NOTHING
                            """,
                            (pid, n_date, tib, tst, sol, despertares, min_n1, min_n2, min_n3, min_rem),
                        )

        conn.commit()
    print("Semilla de 90 participantes UNT insertada correctamente.")
    etl_res = run_etl(origen="seed_inicial", dsn=conn_dsn)
    print("ETL post-semilla:", etl_res)
    export_sample_csvs()


def export_sample_csvs() -> None:
    """Genera 3 archivos CSV de wearable de muestra en sample_csvs/ para pruebas en vivo."""
    out_dir = ROOT_DIR / "sample_csvs"
    out_dir.mkdir(parents=True, exist_ok=True)

    headers = ["fecha", "tib_min", "tst_min", "sol_min", "despertares", "min_n1", "min_n2", "min_n3", "min_rem"]

    # CSV 1: Wearable limpio de 7 noches recientes (ej. para estudiante UNT-001)
    rows_clean = [
        ["2026-11-20", 475, 412, 18, 2, 24, 215, 86, 87],
        ["2026-11-21", 510, 448, 16, 1, 25, 226, 99, 98],
        ["2026-11-22", 495, 430, 19, 2, 26, 220, 92, 92],
        ["2026-11-23", 455, 385, 28, 3, 27, 210, 68, 80],
        ["2026-11-24", 460, 396, 22, 2, 24, 212, 77, 83],
        ["2026-11-25", 470, 418, 15, 1, 22, 214, 92, 90],
        ["2026-11-26", 480, 428, 14, 1, 21, 217, 98, 92],
    ]
    with (out_dir / "wearable_unt001_limpio_7noches.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows_clean)

    # CSV 2: Con errores intencionales para demostrar validacion ETL (RETL-02)
    rows_mixed = [
        ["2026-11-25", 465, 405, 19, 2, 24, 211, 85, 85],
        ["2026-11-26", 400, 430, 20, 2, 25, 220, 90, 95],  # Error: TST+SOL > TIB
        ["2026-11-24", 450, 390, 18, 2, 20, 180, 70, 60],  # Error: suma fases != TST
    ]
    with (out_dir / "wearable_validacion_mixta_demo.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows_mixed)

    # CSV 3: Plantilla vacia con ejemplo
    with (out_dir / "plantilla_wearable_glymphocare.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerow(["2026-11-25", 480, 420, 18, 2, 25, 220, 88, 87])


if __name__ == "__main__":
    seed_database()
