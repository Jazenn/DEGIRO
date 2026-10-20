"""PostgreSQL / Neon database connection management."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator, Optional
import psycopg2
import psycopg2.extras

from backend.config import get_database_url

logger = logging.getLogger(__name__)


@contextmanager
def get_db_connection(database_url: Optional[str] = None) -> Generator[psycopg2.extensions.connection, None, None]:
    """Yield a database connection with automatic commit and rollback."""
    url = database_url or get_database_url()
    if not url:
        raise KeyError("DATABASE_URL is not set in environment.")

    conn = psycopg2.connect(url)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
