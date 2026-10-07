"""Ordered, checksummed and lock-protected PostgreSQL schema migrations."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MIGRATION_FILE_PATTERN = re.compile(r"^(\d{3})_[a-z0-9_]+\.sql$")
# Arbitrary constant shared by every process that migrates this database.
MIGRATION_LOCK_ID = 7_202_627


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    sql: str

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode("utf-8")).hexdigest()


def discover_migrations(directory: Path) -> list[Migration]:
    """Return migrations ordered by their three-digit version prefix."""

    migrations: list[Migration] = []
    for path in sorted(directory.glob("*.sql")):
        match = MIGRATION_FILE_PATTERN.match(path.name)
        if match is None:
            raise ValueError(f"migration file name must look like 001_name.sql: {path.name}")
        migrations.append(
            Migration(
                version=match.group(1),
                name=path.name,
                sql=path.read_text(encoding="utf-8"),
            )
        )
    versions = [migration.version for migration in migrations]
    if len(versions) != len(set(versions)):
        raise ValueError(f"duplicate migration versions in {directory}")
    return migrations


def apply_migrations(connection: Any, migrations: list[Migration]) -> list[str]:
    """Apply pending migrations, each in its own transaction.

    ``connection`` must be an autocommit psycopg connection. A session advisory
    lock serializes concurrent runners, and a changed checksum for an already
    applied migration is treated as an error instead of being silently skipped.
    """

    connection.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK_ID,))
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                checksum TEXT NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        applied = {
            version: checksum
            for version, checksum in connection.execute(
                "SELECT version, checksum FROM schema_migrations"
            ).fetchall()
        }
        newly_applied: list[str] = []
        for migration in migrations:
            if migration.version in applied:
                if applied[migration.version] != migration.checksum:
                    raise RuntimeError(
                        f"applied migration {migration.name} has been modified; "
                        "add a new migration instead"
                    )
                continue
            with connection.transaction():
                connection.execute(migration.sql)
                connection.execute(
                    "INSERT INTO schema_migrations (version, name, checksum) "
                    "VALUES (%s, %s, %s)",
                    (migration.version, migration.name, migration.checksum),
                )
            newly_applied.append(migration.name)
        return newly_applied
    finally:
        connection.execute("SELECT pg_advisory_unlock(%s)", (MIGRATION_LOCK_ID,))
