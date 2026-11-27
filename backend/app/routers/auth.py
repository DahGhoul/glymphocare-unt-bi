from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.database import get_db_conn
from app.core.security import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)
    nombre_display: str = Field(min_length=2)
    edad: int = Field(ge=16, le=65)
    sexo: str
    facultad: str
    carrera: str
    ciclo: int = Field(ge=1, le=12)
    consentimiento_aceptado: bool


@router.post("/login")
def login(body: LoginRequest):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.email, u.password_hash, u.nombre_display, u.rol, u.activo, p.codigo AS participante_codigo
                FROM glympho_oltp.usuario u
                LEFT JOIN glympho_oltp.participante p ON p.usuario_id = u.id
                WHERE LOWER(u.email) = LOWER(%s)
                """,
                (body.email.strip(),),
            )
            user = cur.fetchone()
    if not user or not user["activo"] or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas.")

    token = create_access_token({"sub": str(user["id"]), "rol": user["rol"], "email": user["email"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "nombre_display": user["nombre_display"],
            "rol": user["rol"],
            "participante_codigo": user["participante_codigo"],
        },
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest):
    if not body.consentimiento_aceptado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe aceptar el consentimiento informado para participar en el estudio.",
        )
    if body.sexo not in ("F", "M", "Otro"):
        raise HTTPException(status_code=400, detail="Sexo debe ser F, M u Otro.")

    pw_hash = hash_password(body.password)
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM glympho_oltp.usuario WHERE LOWER(email) = LOWER(%s)", (body.email.strip(),))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="El correo ya se encuentra registrado.")

            cur.execute(
                """
                INSERT INTO glympho_oltp.usuario (email, password_hash, nombre_display, rol, activo)
                VALUES (%s, %s, %s, 'participante', TRUE)
                RETURNING id
                """,
                (body.email.strip().lower(), pw_hash, body.nombre_display.strip()),
            )
            user_id = cur.fetchone()["id"]

            cur.execute("SELECT COALESCE(MAX(id), 0) + 1 AS nxt FROM glympho_oltp.participante")
            nxt = int(cur.fetchone()["nxt"])
            codigo = f"UNT-{nxt:03d}"

            cur.execute(
                """
                INSERT INTO glympho_oltp.participante (usuario_id, codigo, edad, sexo, facultad, carrera, ciclo)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (user_id, codigo, body.edad, body.sexo, body.facultad, body.carrera, body.ciclo),
            )
            part_id = cur.fetchone()["id"]

            cur.execute(
                """
                INSERT INTO glympho_oltp.consentimiento (participante_id, version_texto, aceptado)
                VALUES (%s, 'v1.0-UNT-2026', TRUE)
                """,
                (part_id,),
            )
        conn.commit()

    token = create_access_token({"sub": str(user_id), "rol": "participante", "email": body.email.strip().lower()})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "email": body.email.strip().lower(),
            "nombre_display": body.nombre_display.strip(),
            "rol": "participante",
            "participante_codigo": codigo,
        },
    }


@router.get("/me")
def me(user=Depends(get_current_user)):
    return user
