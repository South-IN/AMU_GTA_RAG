"""Load the approved retrieval corpora from PostgreSQL or local JSON artifacts."""

from __future__ import annotations

import os

from amu_admissions_rag.config import AppPaths
from amu_admissions_rag.models import CourseCorpus, IndexCorpus

DATABASE_URL_ENV = "AMU_RAG_DATABASE_URL"
APPROVED_INDEX_NAME = "guide-2026-27.index-corpus.approved.json"
REVIEWED_COURSES_NAME = "guide-2026-27.course-corpus.reviewed.json"


def load_approved_corpora(
    paths: AppPaths | None = None,
) -> tuple[IndexCorpus, CourseCorpus]:
    """Return the approved index and reviewed courses.

    PostgreSQL is the system of record whenever ``AMU_RAG_DATABASE_URL`` is set,
    as it is inside Docker Compose. Without it, the local JSON artifacts written
    by the ingestion pipeline are used so offline development keeps working.
    """

    database_url = os.environ.get(DATABASE_URL_ENV, "").strip()
    if database_url:
        from amu_admissions_rag.storage import PostgresIndexStore

        return PostgresIndexStore(database_url).load_approved_corpora(
            os.environ.get("AMU_RAG_DOCUMENT_ID") or None
        )

    paths = paths or AppPaths.from_package()
    index = IndexCorpus.model_validate_json(
        (paths.processed_dir / APPROVED_INDEX_NAME).read_text(encoding="utf-8")
    )
    courses = CourseCorpus.model_validate_json(
        (paths.review_dir / REVIEWED_COURSES_NAME).read_text(encoding="utf-8")
    )
    return index, courses
