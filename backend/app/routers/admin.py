from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import get_settings
from app.core.database import get_db_conn
from app.core.security import require_roles
from etl.run_etl import run_etl

router = APIRouter(prefix="/api/admin", tags=["admin"])
admin_only = require_roles(["admin"])


class RulePayload(BaseModel):
    kpi_codigo: str
    operador: str
    umbral: float
    severidad: str
    titulo: str
    texto_recomendacion: str
    activo: bool = True


class RoleUpdatePayload(BaseModel):
    rol: str
    activo: Optional[bool] = None


class AiConfigPayload(BaseModel):
    gemini_api_key: str = ""


@router.get("/rules")
def list_rules(user=Depends(admin_only)):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM glympho_oltp.recomendacion_regla ORDER BY kpi_codigo, id")
            return cur.fetchall()


@router.post("/rules")
def create_rule(body: RulePayload, user=Depends(admin_only)):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO glympho_oltp.recomendacion_regla
                    (kpi_codigo, operador, umbral, severidad, titulo, texto_recomendacion, activo)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (body.kpi_codigo, body.operador, body.umbral, body.severidad, body.titulo, body.texto_recomendacion, body.activo),
            )
            created = cur.fetchone()
        conn.commit()
    return created


@router.put("/rules/{rule_id}")
def update_rule(rule_id: int, body: RulePayload, user=Depends(admin_only)):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE glympho_oltp.recomendacion_regla
                SET kpi_codigo = %s, operador = %s, umbral = %s, severidad = %s,
                    titulo = %s, texto_recomendacion = %s, activo = %s, actualizado_en = NOW()
                WHERE id = %s
                RETURNING *
                """,
                (body.kpi_codigo, body.operador, body.umbral, body.severidad, body.titulo, body.texto_recomendacion, body.activo, rule_id),
            )
            updated = cur.fetchone()
        conn.commit()
    if not updated:
        raise HTTPException(status_code=404, detail="Regla no encontrada.")
    return updated


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, user=Depends(admin_only)):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM glympho_oltp.recomendacion_regla WHERE id = %s RETURNING id", (rule_id,))
            deleted = cur.fetchone()
        conn.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Regla no encontrada.")
    return {"deleted": rule_id}


@router.get("/users")
def list_users(user=Depends(admin_only)):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.email, u.nombre_display, u.rol, u.activo, u.creado_en, p.codigo AS participante_codigo
                FROM glympho_oltp.usuario u
                LEFT JOIN glympho_oltp.participante p ON p.usuario_id = u.id
                ORDER BY u.id
                """
            )
            rows = cur.fetchall()
    return [{**r, "creado_en": r["creado_en"].isoformat()} for r in rows]


@router.patch("/users/{user_id}/role")
def update_user_role(user_id: int, body: RoleUpdatePayload, user=Depends(admin_only)):
    if body.rol not in ("participante", "investigador", "analista", "admin"):
        raise HTTPException(status_code=400, detail="Rol invalido.")
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE glympho_oltp.usuario
                SET rol = %s, activo = COALESCE(%s, activo)
                WHERE id = %s
                RETURNING id, email, nombre_display, rol, activo
                """,
                (body.rol, body.activo, user_id),
            )
            updated = cur.fetchone()
        conn.commit()
    if not updated:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    return updated


@router.post("/etl/run")
def trigger_etl(user=Depends(admin_only)):
    settings = get_settings()
    return run_etl(origen=f"admin_panel:{user['email']}", dsn=settings.pg_dsn)


@router.get("/etl/logs")
def etl_logs(user=Depends(admin_only)):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM glympho_dw.etl_ejecucion_log ORDER BY id DESC LIMIT 20")
            rows = cur.fetchall()
    return [
        {**r, "inicio": r["inicio"].isoformat(), "fin": r["fin"].isoformat() if r["fin"] else None}
        for r in rows
    ]


@router.get("/ai-config")
def get_ai_config(user=Depends(admin_only)):
    settings = get_settings()
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT valor FROM glympho_oltp.configuracion_sistema WHERE clave = 'gemini_api_key'")
            row = cur.fetchone()
    db_key = row["valor"] if row else ""
    effective = db_key or settings.gemini_api_key
    return {
        "configured": bool(effective),
        "model": settings.gemini_model,
        "masked_key": (effective[:6] + "..." + effective[-4:]) if len(effective) > 10 else "",
    }


@router.put("/ai-config")
def set_ai_config(body: AiConfigPayload, user=Depends(admin_only)):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO glympho_oltp.configuracion_sistema (clave, valor, actualizado_en)
                VALUES ('gemini_api_key', %s, NOW())
                ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor, actualizado_en = NOW()
                """,
                (body.gemini_api_key.strip(),),
            )
        conn.commit()
    return {"configured": bool(body.gemini_api_key.strip())}
