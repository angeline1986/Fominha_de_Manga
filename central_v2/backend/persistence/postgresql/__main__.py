"""Small explicit CLI for health checks and reversible migrations."""

from __future__ import annotations

import argparse
import json
import os

from .config import PostgresSettings
from .db import check_connection, connect
from .migrations import discover, migrate_down, migrate_up


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "up", "down", "status"))
    parser.add_argument("--target", help="apply migrations through this three-digit version")
    args = parser.parse_args()
    if args.action == "check":
        print(json.dumps(check_connection(), indent=2))
        return 0
    settings = None
    migration_dsn = os.environ.get("FOMINHA_PG_MIGRATION_DSN", "").strip()
    if args.action in ("up", "down") and migration_dsn:
        settings = PostgresSettings(migration_dsn)
    with connect(settings) as conn:
        if args.action == "up":
            print(json.dumps({"applied": migrate_up(conn, target=args.target)}))
        elif args.action == "down":
            print(json.dumps({"rolled_back": migrate_down(conn)}))
        else:
            rows = conn.execute(
                "SELECT version,name,checksum,applied_at FROM public.fominha_schema_migrations ORDER BY version"
            ).fetchall()
            print(json.dumps([tuple(row) for row in rows], default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
