from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

import psycopg
from psycopg.rows import dict_row

from app.core.config import get_settings


@contextmanager
def get_db_conn() -> Generator[psycopg.Connection, None, None]:
    settings = get_settings()
    with psycopg.connect(settings.pg_dsn, row_factory=dict_row) as conn:
        yield conn
