from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.database import get_db_conn

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(payload: Dict[str, Any]) -> str:
    settings = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    to_encode = {**payload, "exp": exp}
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm="HS256")


def decode_token(token: str) -> Dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesion invalida o expirada.",
        ) from exc


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Dict[str, Any]:
    if not creds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticacion requerida.",
        )
    data = decode_token(creds.credentials)
    user_id = data.get("sub")
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.email, u.nombre_display, u.rol, u.activo, p.codigo AS participante_codigo
                FROM glympho_oltp.usuario u
                LEFT JOIN glympho_oltp.participante p ON p.usuario_id = u.id
                WHERE u.id = %s
                """,
                (int(user_id),),
            )
            user = cur.fetchone()
    if not user or not user["activo"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no disponible.")
    return user


def require_roles(allowed: Iterable[str]):
    allowed_set = set(allowed)

    def _checker(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        if user["rol"] not in allowed_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso restringido. Se requiere rol: {', '.join(sorted(allowed_set))}.",
            )
        return user

    return _checker
