"""Tests de integracion End-to-End de la API FastAPI de GlymphoCare contra PostgreSQL."""

from __future__ import annotations

import io
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
for p in (str(ROOT_DIR), str(BACKEND_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.main import app

client = TestClient(app)


def _login(email: str, password: str = "Glympho2026!") -> str:
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def test_health_and_dashboards():
    h = client.get("/api/health")
    assert h.status_code == 200
    assert h.json()["participantes"] >= 90
    assert h.json()["noches"] >= 2250

    token = _login("analista@glymphocare.edu.pe")
    headers = {"Authorization": f"Bearer {token}"}

    for endpoint in [
        "/api/dashboard/filters",
        "/api/dashboard/executive",
        "/api/dashboard/subjective",
        "/api/dashboard/glymphatic",
        "/api/dashboard/habits",
        "/api/dashboard/participants",
        "/api/dashboard/participants/UNT-001",
    ]:
        r = client.get(endpoint, headers=headers)
        assert r.status_code == 200, f"{endpoint} failed: {r.text}"

    habits = client.get("/api/dashboard/habits", headers=headers).json()
    assert len(habits["findings"]) >= 3
    assert any(f["significativo"] for f in habits["findings"])


def test_reports_preview_and_pdf_csv_export():
    token = _login("analista@glymphocare.edu.pe")
    headers = {"Authorization": f"Bearer {token}"}

    for rtype in ["cohorte", "dias_semana", "habitos"]:
        prev = client.get(f"/api/reports/preview/{rtype}", headers=headers)
        assert prev.status_code == 200
        assert len(prev.json()["rows"]) > 3

        pdf_resp = client.post(
            "/api/reports/export",
            headers=headers,
            json={"report_type": rtype, "format": "pdf", "filters": {}},
        )
        assert pdf_resp.status_code == 200
        assert pdf_resp.content.startswith(b"%PDF")

        csv_resp = client.post(
            "/api/reports/export",
            headers=headers,
            json={"report_type": rtype, "format": "csv", "filters": {}},
        )
        assert csv_resp.status_code == 200
        assert len(csv_resp.content) > 100


def test_rbac_and_admin_rules():
    part_token = _login("estudiante@glymphocare.edu.pe")
    r_forbidden = client.get("/api/admin/rules", headers={"Authorization": f"Bearer {part_token}"})
    assert r_forbidden.status_code == 403

    admin_token = _login("admin@glymphocare.edu.pe")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    rules = client.get("/api/admin/rules", headers=admin_headers)
    assert rules.status_code == 200
    assert len(rules.json()) >= 8

    logs = client.get("/api/admin/etl/logs", headers=admin_headers)
    assert logs.status_code == 200
    assert len(logs.json()) >= 1


def test_csv_upload_validation_and_ai_interpret():
    token = _login("investigador@glymphocare.edu.pe")
    headers = {"Authorization": f"Bearer {token}"}

    csv_content = (
        "fecha,tib_min,tst_min,sol_min,despertares,min_n1,min_n2,min_n3,min_rem\n"
        "2026-11-26,480,420,18,1,24,214,92,90\n"
        "2026-11-25,400,430,20,2,25,220,90,95\n"
    ).encode("utf-8")

    up = client.post(
        "/api/capture/sleep-csv",
        headers=headers,
        data={"participante_codigo": "UNT-001"},
        files={"file": ("test_wearable.csv", io.BytesIO(csv_content), "text/csv")},
    )
    assert up.status_code == 200, up.text
    body = up.json()
    assert body["registros_validos"] == 1
    assert body["registros_rechazados"] == 1
    assert body["etl"]["estado"] == "completado"

    ai_resp = client.post(
        "/api/ai/interpret",
        headers=headers,
        json={"scope": "participant", "codigo": "UNT-001"},
    )
    assert ai_resp.status_code == 200, ai_resp.text
    ai_json = ai_resp.json()
    assert "resumen_ejecutivo" in ai_json
    assert "analisis_glinfatico_n3" in ai_json
    assert len(ai_json["plan_accion"]) >= 1


def test_sql_evidence_and_habit_simulator():
    token = _login("analista@glymphocare.edu.pe")
    headers = {"Authorization": f"Bearer {token}"}

    q_list = client.get("/api/reports/sql-evidence", headers=headers)
    assert q_list.status_code == 200
    assert len(q_list.json()) == 4

    sql_run = client.post("/api/reports/sql-evidence/run", headers=headers, json={"query_id": "q1_kpis"})
    assert sql_run.status_code == 200, sql_run.text
    sdata = sql_run.json()
    assert sdata["row_count"] == 1
    assert sdata["rows"][0]["total_participantes"] >= 90

    sim = client.post(
        "/api/dashboard/simulate-habits",
        headers=headers,
        json={
            "pantallas": "<=1h",
            "cafeina": "antes_14h_o_ninguna",
            "ejercicio": ">=3_dias",
            "estres": "bajo",
            "wake_time": "06:45",
        },
    )
    assert sim.status_code == 200, sim.text
    sim_json = sim.json()
    assert "proyeccion" in sim_json
    assert "horario_recomendado" in sim_json
    assert sim_json["proyeccion"]["pct_n3"] >= sim_json["linea_base"]["pct_n3"]
