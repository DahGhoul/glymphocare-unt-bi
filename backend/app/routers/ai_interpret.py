from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.database import get_db_conn
from app.core.security import get_current_user
from app.routers.dashboard import executive_dashboard, participant_detail
from app.services.llm_service import generate_ai_interpretation

router = APIRouter(prefix="/api/ai", tags=["ai"])


class InterpretRequest(BaseModel):
    scope: str = "cohort"  # cohort | participant
    codigo: Optional[str] = None


@router.post("/interpret")
async def interpret_sleep(body: InterpretRequest, user=Depends(get_current_user)):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT valor FROM glympho_oltp.configuracion_sistema WHERE clave = 'gemini_api_key'")
            row = cur.fetchone()
            runtime_key = row["valor"] if row else ""

    if body.scope == "participant":
        if not body.codigo:
            raise HTTPException(status_code=400, detail="Debe indicar codigo de participante.")
        detail = participant_detail(body.codigo, user=user)
        payload = {
            "codigo": detail["participante"]["codigo"],
            "carrera": detail["participante"]["carrera"],
            "kpis": detail["kpis"],
            "habitos": detail["habitos_actuales"],
            "alerts": detail["alerts"],
        }
    else:
        summary = executive_dashboard(filters={}, user=user)
        payload = {
            "n": summary["n_participantes"],
            "noches": summary["n_noches"],
            "kpis": summary["kpis"],
            "alerts": summary["alerts"],
        }

    return await generate_ai_interpretation(body.scope, payload, runtime_api_key=runtime_key)
