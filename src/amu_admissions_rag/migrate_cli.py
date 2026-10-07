"""Apply pending PostgreSQL schema migrations."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from amu_admissions_rag.config import AppPaths
from amu_admissions_rag.corpus import DATABASE_URL_ENV
from amu_admissions_rag.storage import PostgresIndexStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply numbered SQL migrations")
    parser.add_argument("--migrations-dir", type=Path, help="Default: sql/")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    database_url = os.environ.get(DATABASE_URL_ENV, "")
    if not database_url:
        raise SystemExit(f"{DATABASE_URL_ENV} is required")
    migrations_dir = args.migrations_dir or AppPaths.from_package().project_root / "sql"
    applied = PostgresIndexStore(database_url).apply_migrations(migrations_dir)
    print(f"Applied {len(applied)} migration(s): {', '.join(applied) or 'none pending'}")


if __name__ == "__main__":
    main()
