from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://glympho:glympho_secret_2026@localhost:5433/glymphocare"
    jwt_secret_key: str = "glymphocare-unt-local-dev-key-2026-g5"
    jwt_expire_minutes: int = 720
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3-flash-preview"
    aws_region: str = "us-east-1"
    aws_s3_bucket: str = ""
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def pg_dsn(self) -> str:
        return self.database_url.replace("postgresql+psycopg://", "postgresql://")

    @property
    def cors_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
