"""Approval-gated PostgreSQL corpus loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from amu_admissions_rag.indexing import RetrievalChunkBuilder
from amu_admissions_rag.models import (
    ChunkType,
    CourseCorpus,
    PolicyCorpus,
    ReviewStatus,
)


class PostgresIndexStore:
    """Replace one document's approved records and retrieval chunks atomically."""

    def __init__(self, database_url: str) -> None:
        if not database_url.strip():
            raise ValueError("database_url cannot be empty")
        self.database_url = database_url

    def apply_schema(self, schema_path: Path) -> None:
        schema = schema_path.read_text(encoding="utf-8")
        psycopg, _ = self._driver()
        with psycopg.connect(self.database_url, autocommit=True) as connection:
            connection.execute(schema)

    def replace_approved_corpus(
        self,
        course_corpus: CourseCorpus,
        policy_corpus: PolicyCorpus,
        *,
        allow_empty: bool = False,
    ) -> int:
        index_corpus = RetrievalChunkBuilder().build(course_corpus, policy_corpus)
        if not index_corpus.chunks and not allow_empty:
            raise ValueError(
                "no approved chunks found; refusing to replace the database corpus"
            )
        if any(
            chunk.review.status is not ReviewStatus.APPROVED
            for chunk in index_corpus.chunks
        ):
            raise ValueError("retrieval index may contain approved chunks only")

        approved_courses = [
            record
            for record in course_corpus.courses
            if record.review.status is ReviewStatus.APPROVED
        ]
        approved_sections = [
            record
            for record in policy_corpus.sections
            if record.review.status is ReviewStatus.APPROVED
        ]
        approved_appendices = [
            record
            for record in policy_corpus.appendix_rows
            if record.review.status is ReviewStatus.APPROVED
        ]

        psycopg, jsonb = self._driver()
        document = index_corpus.document
        with psycopg.connect(self.database_url) as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO documents (
                            document_id, filename, academic_year, sha256, total_pages
                        ) VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (document_id) DO UPDATE SET
                            filename = EXCLUDED.filename,
                            academic_year = EXCLUDED.academic_year,
                            sha256 = EXCLUDED.sha256,
                            total_pages = EXCLUDED.total_pages
                        """,
                        (
                            document.document_id,
                            document.filename,
                            document.academic_year,
                            document.sha256,
                            document.total_pages,
                        ),
                    )
                    self._delete_document_records(cursor, document.document_id)
                    self._insert_courses(cursor, approved_courses, jsonb)
                    self._insert_sections(cursor, approved_sections, jsonb)
                    self._insert_appendices(cursor, approved_appendices, jsonb)
                    self._insert_chunks(cursor, index_corpus.chunks, jsonb)
        return len(index_corpus.chunks)

    @staticmethod
    def _delete_document_records(cursor: Any, document_id: str) -> None:
        cursor.execute(
            "DELETE FROM retrieval_chunks WHERE document_id = %s",
            (document_id,),
        )
        cursor.execute(
            "DELETE FROM appendix_records WHERE document_id = %s",
            (document_id,),
        )
        cursor.execute(
            "DELETE FROM policy_sections WHERE document_id = %s",
            (document_id,),
        )
        cursor.execute(
            "DELETE FROM course_records WHERE document_id = %s",
            (document_id,),
        )

    @staticmethod
    def _insert_courses(cursor: Any, records: list[Any], jsonb: Any) -> None:
        cursor.executemany(
            """
            INSERT INTO course_records (
                record_id, document_id, course_name, course_code, faculty,
                program_level, campus, physical_page, printed_page, content,
                review_status, reviewer, reviewed_at, review_notes
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            """,
            [
                (
                    record.record_id,
                    record.document_id,
                    record.course_name,
                    record.course_code,
                    record.faculty,
                    record.program_level.value,
                    record.campus,
                    record.source.physical_page,
                    record.source.printed_page,
                    jsonb(record.model_dump(mode="json")),
                    record.review.status.value,
                    record.review.reviewer,
                    record.review.reviewed_at,
                    record.review.notes,
                )
                for record in records
            ],
        )

    @staticmethod
    def _insert_sections(cursor: Any, records: list[Any], jsonb: Any) -> None:
        cursor.executemany(
            """
            INSERT INTO policy_sections (
                record_id, document_id, heading, physical_page, printed_page,
                content, review_status, reviewer, reviewed_at, review_notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                (
                    record.record_id,
                    record.document_id,
                    record.heading,
                    record.source.physical_page,
                    record.source.printed_page,
                    jsonb(record.model_dump(mode="json")),
                    record.review.status.value,
                    record.review.reviewer,
                    record.review.reviewed_at,
                    record.review.notes,
                )
                for record in records
            ],
        )

    @staticmethod
    def _insert_appendices(cursor: Any, records: list[Any], jsonb: Any) -> None:
        cursor.executemany(
            """
            INSERT INTO appendix_records (
                record_id, document_id, appendix_type, course_name, course_code,
                physical_page, printed_page, content, review_status, reviewer,
                reviewed_at, review_notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                (
                    record.record_id,
                    record.document_id,
                    record.appendix_type.value,
                    record.course_name,
                    record.course_code,
                    record.source.physical_page,
                    record.source.printed_page,
                    jsonb(record.model_dump(mode="json")),
                    record.review.status.value,
                    record.review.reviewer,
                    record.review.reviewed_at,
                    record.review.notes,
                )
                for record in records
            ],
        )

    @staticmethod
    def _insert_chunks(cursor: Any, records: list[Any], jsonb: Any) -> None:
        course_types = {
            ChunkType.COURSE_OVERVIEW,
            ChunkType.COURSE_FIELD,
            ChunkType.COURSE_TABLE_ROW,
        }
        cursor.executemany(
            """
            INSERT INTO retrieval_chunks (
                chunk_id, document_id, chunk_type, source_record_id,
                parent_course_id, field_name, title, content, physical_page,
                printed_page, metadata, review_status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                (
                    record.chunk_id,
                    record.document_id,
                    record.chunk_type.value,
                    record.parent_record_id,
                    (
                        record.parent_record_id
                        if record.chunk_type in course_types
                        else None
                    ),
                    record.field_name,
                    record.title,
                    record.text,
                    record.source.physical_page,
                    record.source.printed_page,
                    jsonb(record.metadata),
                    record.review.status.value,
                )
                for record in records
            ],
        )

    @staticmethod
    def _driver() -> tuple[Any, Any]:
        try:
            import psycopg
            from psycopg.types.json import Jsonb
        except ImportError as error:
            raise RuntimeError(
                "PostgreSQL loading requires the project database dependencies"
            ) from error
        return psycopg, Jsonb
