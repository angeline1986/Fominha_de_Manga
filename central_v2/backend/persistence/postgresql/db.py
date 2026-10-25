"""Connection, transaction and health-check helpers."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg import Connection
from psycopg.pq import TransactionStatus

from .config import PostgresSettings


def connect(settings: PostgresSettings | None = None) -> Connection:
    selected = settings or PostgresSettings.from_env()
    return psycopg.connect(selected.conninfo, autocommit=False)


@contextmanager
def transaction(conn: Connection, isolation: str = "READ COMMITTED") -> Iterator[Connection]:
    allowed = {"READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE"}
    normalized = isolation.upper()
    if normalized not in allowed:
        raise ValueError(f"Unsupported isolation level: {isolation}")
    top_level = conn.info.transaction_status == TransactionStatus.IDLE
    with conn.transaction():
        if top_level:
            conn.execute(f"SET TRANSACTION ISOLATION LEVEL {normalized}")
        yield conn


def check_connection(settings: PostgresSettings | None = None) -> dict[str, str]:
    with connect(settings) as conn:
        row = conn.execute("SELECT current_database(), current_user, version()").fetchone()
    return {"database": row[0], "user": row[1], "server_version": row[2]}
