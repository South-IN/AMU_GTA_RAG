"""Load approved source records and chunks into PostgreSQL."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from amu_admissions_rag.config import AppPaths
from amu_admissions_rag.models import CourseCorpus, PolicyCorpus
from amu_admissions_rag.storage import PostgresIndexStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Atomically replace one guide's approved PostgreSQL corpus"
    )
    parser.add_argument("--courses", type=Path, help="Reviewed course-corpus JSON")
    parser.add_argument("--policies", type=Path, help="Reviewed policy-corpus JSON")
    parser.add_argument(
        "--apply-schema",
        action="store_true",
        help="Apply pending numbered migrations from sql/ before loading",
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Allow replacing the document with zero approved chunks",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    paths = AppPaths.from_package()
    database_url = os.environ.get("AMU_RAG_DATABASE_URL", "")
    if not database_url:
        raise SystemExit("AMU_RAG_DATABASE_URL is required")

    course_path = (
        args.courses
        or paths.review_dir / "guide-2026-27.course-corpus.pending.json"
    )
    policy_path = (
        args.policies
        or paths.review_dir / "guide-2026-27.policy-corpus.pending.json"
    )

    courses = CourseCorpus.model_validate_json(course_path.read_text(encoding="utf-8"))
    policies = PolicyCorpus.model_validate_json(policy_path.read_text(encoding="utf-8"))
    store = PostgresIndexStore(database_url)
    if args.apply_schema:
        store.apply_migrations(paths.project_root / "sql")
    count = store.replace_approved_corpus(
        courses,
        policies,
        allow_empty=args.allow_empty,
    )
    print(f"Loaded {count} approved retrieval chunk(s) into PostgreSQL")


if __name__ == "__main__":
    main()
