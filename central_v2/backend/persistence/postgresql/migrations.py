"""Transactional, checksummed SQL migrations with explicit down scripts."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from psycopg import Connection
from psycopg.rows import dict_row

MIGRATION_LOCK = 741_082_113_550
MIGRATION_DIR = Path(__file__).with_name("migrations")
NAME_PATTERN = re.compile(r"^(\d{3})_([a-z0-9_]+)\.up\.sql$")


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    up_path: Path
    down_path: Path

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.up_path.read_bytes()).hexdigest()


def discover(directory: Path = MIGRATION_DIR) -> list[Migration]:
    migrations = []
    for up_path in sorted(directory.glob("*.up.sql")):
        match = NAME_PATTERN.fullmatch(up_path.name)
        if not match:
            raise ValueError(f"Invalid migration filename: {up_path.name}")
        version, name = match.groups()
        down_path = up_path.with_name(f"{version}_{name}.down.sql")
        if not down_path.is_file():
            raise FileNotFoundError(f"Missing rollback migration: {down_path}")
        migrations.append(Migration(version, name, up_path, down_path))
    if len({item.version for item in migrations}) != len(migrations):
        raise ValueError("Migration versions must be unique")
    return migrations


def _ensure_table(conn: Connection) -> None:
    conn.execute("""CREATE TABLE IF NOT EXISTS public.fominha_schema_migrations (
        version text PRIMARY KEY, name text NOT NULL, checksum char(64) NOT NULL,
        applied_at timestamptz NOT NULL DEFAULT now())""")


def _applied(conn: Connection) -> dict[str, dict[str, object]]:
    _ensure_table(conn)
    rows = conn.cursor(row_factory=dict_row).execute(
        "SELECT version,name,checksum FROM public.fominha_schema_migrations"
    ).fetchall()
    return {row["version"]: row for row in rows}


def migrate_up(conn: Connection, target: str | None = None, directory: Path = MIGRATION_DIR) -> list[str]:
    migrations = discover(directory)
    if target is not None and target not in {item.version for item in migrations}:
        raise ValueError(f"Unknown migration target: {target}")
    applied_now = []
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK,))
        applied = _applied(conn)
        for migration in migrations:
            if migration.version in applied:
                if applied[migration.version]["checksum"] != migration.checksum:
                    raise RuntimeError(f"Applied migration checksum changed: {migration.version}")
                continue
            if target is not None and migration.version > target:
                break
            conn.execute(migration.up_path.read_text())
            conn.execute("INSERT INTO public.fominha_schema_migrations(version,name,checksum) VALUES (%s,%s,%s)",
                         (migration.version, migration.name, migration.checksum))
            applied_now.append(migration.version)
    return applied_now


def migrate_down(conn: Connection, directory: Path = MIGRATION_DIR) -> str | None:
    migrations = {item.version: item for item in discover(directory)}
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK,))
        _ensure_table(conn)
        row = conn.cursor(row_factory=dict_row).execute(
            "SELECT version FROM public.fominha_schema_migrations ORDER BY version DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        migration = migrations[row["version"]]
        conn.execute(migration.down_path.read_text())
        conn.execute("DELETE FROM public.fominha_schema_migrations WHERE version=%s", (migration.version,))
        return migration.version
