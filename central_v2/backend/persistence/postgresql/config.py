"""Environment-only PostgreSQL configuration; never reads operational JSON."""

from __future__ import annotations

import os
from dataclasses import dataclass

from psycopg.conninfo import make_conninfo


@dataclass(frozen=True)
class PostgresSettings:
    conninfo: str
    connect_timeout: int = 5

    @classmethod
    def from_env(cls) -> "PostgresSettings":
        dsn = os.environ.get("FOMINHA_PG_DSN", "").strip()
        timeout = int(os.environ.get("FOMINHA_PG_CONNECT_TIMEOUT", "5"))
        if timeout < 1 or timeout > 60:
            raise ValueError("FOMINHA_PG_CONNECT_TIMEOUT must be between 1 and 60")
        if dsn:
            return cls(make_conninfo(dsn, connect_timeout=timeout), timeout)
        required = ("FOMINHA_PG_DATABASE", "FOMINHA_PG_USER")
        missing = [key for key in required if not os.environ.get(key, "").strip()]
        if missing:
            raise ValueError(f"Missing PostgreSQL environment settings: {', '.join(missing)}")
        values = {
            "host": os.environ.get("FOMINHA_PG_HOST", "127.0.0.1"),
            "port": int(os.environ.get("FOMINHA_PG_PORT", "5432")),
            "dbname": os.environ["FOMINHA_PG_DATABASE"],
            "user": os.environ["FOMINHA_PG_USER"],
            "application_name": os.environ.get("FOMINHA_PG_APP_NAME", "fominha-central-v2"),
            "sslmode": os.environ.get("FOMINHA_PG_SSLMODE", "prefer"),
            "connect_timeout": timeout,
        }
        password = os.environ.get("FOMINHA_PG_PASSWORD")
        if password:
            values["password"] = password
        return cls(make_conninfo(**values), timeout)
