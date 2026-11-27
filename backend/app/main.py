from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import get_db_conn
from app.routers import admin, ai_interpret, auth, capture, dashboard, reports

settings = get_settings()

app = FastAPI(
    title="GlymphoCare BI API",
    description="API analitica para medicion de calidad del sueno y limpieza cerebral (%N3) - UNT Grupo G5",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(capture.router)
app.include_router(dashboard.router)
app.include_router(reports.router)
app.include_router(ai_interpret.router)
app.include_router(admin.router)


@app.get("/api/health")
def health():
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM glympho_dw.fact_sueno_noche")
            noches = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) AS n FROM glympho_dw.dim_participante")
            parts = cur.fetchone()["n"]
    return {"status": "ok", "database": "postgresql", "participantes": parts, "noches": noches}
