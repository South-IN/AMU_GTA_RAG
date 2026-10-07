"""Approval-gated PostgreSQL corpus loading and reading."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from amu_admissions_rag.indexing import RetrievalChunkBuilder
from amu_admissions_rag.models import (
    ChunkType,
    CourseCorpus,
    CourseRecord,
    DocumentRecord,
    IndexCorpus,
    PolicyCorpus,
    RetrievalChunk,
    ReviewMetadata,
    ReviewStatus,
    SourceReference,
)
from amu_admissions_rag.retrieval.embedding import (
    EmbeddingProvider,
    HashingEmbeddingProvider,
)
from amu_admissions_rag.storage.migrations import apply_migrations, discover_migrations


@dataclass(frozen=True)
class IngestionRun:
    """Audit details recorded alongside an atomic corpus replacement."""

    fingerprint: str
    pipeline_version: str
    review_batches: list[dict[str, str]] = field(default_factory=list)


class PostgresIndexStore:
    """Replace and read one document's approved records and retrieval chunks."""

    def __init__(self, database_url: str) -> None:
        if not database_url.strip():
            raise ValueError("database_url cannot be empty")
        self.database_url = database_url

    def apply_migrations(self, migrations_dir: Path) -> list[str]:
        """Apply pending numbered migrations and return the newly applied names."""

        psycopg, _ = self._driver()
        migrations = discover_migrations(migrations_dir)
        with psycopg.connect(self.database_url, autocommit=True) as connection:
            return apply_migrations(connection, migrations)

    def latest_ingestion_fingerprint(self, document_id: str) -> str | None:
        psycopg, _ = self._driver()
        with psycopg.connect(self.database_url) as connection:
            row = connection.execute(
                """
                SELECT fingerprint FROM ingestion_runs
                WHERE document_id = %s
                ORDER BY loaded_at DESC, run_id DESC
                LIMIT 1
                """,
                (document_id,),
            ).fetchone()
        return row[0] if row else None

    def replace_approved_corpus(
        self,
        course_corpus: CourseCorpus,
        policy_corpus: PolicyCorpus,
        *,
        allow_empty: bool = False,
        ingestion: IngestionRun | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> int:
        embedding_provider = embedding_provider or HashingEmbeddingProvider()
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
                    self._insert_chunks(
                        cursor,
                        index_corpus.chunks,
                        jsonb,
                        embedding_provider,
                    )
                    if ingestion is not None:
                        cursor.execute(
                            """
                            INSERT INTO ingestion_runs (
                                document_id, fingerprint, pipeline_version,
                                embedding_model, review_batches, course_records,
                                policy_sections, appendix_records, retrieval_chunks
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                document.document_id,
                                ingestion.fingerprint,
                                ingestion.pipeline_version,
                                embedding_provider.name,
                                jsonb(ingestion.review_batches),
                                len(approved_courses),
                                len(approved_sections),
                                len(approved_appendices),
                                len(index_corpus.chunks),
                            ),
                        )
        return len(index_corpus.chunks)

    def load_approved_corpora(
        self,
        document_id: str | None = None,
    ) -> tuple[IndexCorpus, CourseCorpus]:
        """Rebuild the approved retrieval index and course records from PostgreSQL."""

        psycopg, _ = self._driver()
        with psycopg.connect(self.database_url) as connection:
            document_id = document_id or self._default_document_id(connection)
            row = connection.execute(
                """
                SELECT document_id, filename, academic_year, sha256, total_pages
                FROM documents WHERE document_id = %s
                """,
                (document_id,),
            ).fetchone()
            if row is None:
                raise LookupError(f"document {document_id!r} is not loaded")
            document = DocumentRecord(
                document_id=row[0],
                filename=row[1],
                academic_year=row[2],
                sha256=row[3],
                total_pages=row[4],
            )
            courses = [
                CourseRecord.model_validate(content)
                for (content,) in connection.execute(
                    """
                    SELECT content FROM course_records
                    WHERE document_id = %s
                    ORDER BY load_position NULLS LAST, record_id
                    """,
                    (document_id,),
                ).fetchall()
            ]
            chunk_rows = connection.execute(
                """
                SELECT
                    chunk.chunk_id,
                    chunk.document_id,
                    chunk.chunk_type::text,
                    chunk.source_record_id,
                    chunk.field_name,
                    chunk.title,
                    chunk.content,
                    chunk.physical_page,
                    chunk.printed_page,
                    chunk.source,
                    chunk.metadata,
                    coalesce(
                        course.content -> 'review',
                        section.content -> 'review',
                        appendix.content -> 'review'
                    )
                FROM retrieval_chunks AS chunk
                LEFT JOIN course_records AS course
                    ON course.record_id = chunk.source_record_id
                LEFT JOIN policy_sections AS section
                    ON section.record_id = chunk.source_record_id
                LEFT JOIN appendix_records AS appendix
                    ON appendix.record_id = chunk.source_record_id
                WHERE chunk.document_id = %s
                ORDER BY chunk.load_position NULLS LAST, chunk.chunk_id
                """,
                (document_id,),
            ).fetchall()
        chunks = [self._chunk_from_row(chunk_row) for chunk_row in chunk_rows]
        return (
            IndexCorpus(document=document, chunks=chunks),
            CourseCorpus(document=document, courses=courses),
        )

    @staticmethod
    def _default_document_id(connection: Any) -> str:
        row = connection.execute(
            "SELECT document_id FROM ingestion_runs ORDER BY loaded_at DESC, run_id DESC LIMIT 1"
        ).fetchone()
        if row:
            return row[0]
        rows = connection.execute("SELECT document_id FROM documents").fetchall()
        if len(rows) != 1:
            raise LookupError(
                "cannot choose a document: run the ingestion pipeline first "
                f"({len(rows)} document(s) loaded)"
            )
        return rows[0][0]

    @staticmethod
    def _chunk_from_row(row: tuple[Any, ...]) -> RetrievalChunk:
        (
            chunk_id,
            document_id,
            chunk_type,
            source_record_id,
            field_name,
            title,
            content,
            physical_page,
            printed_page,
            source,
            metadata,
            review,
        ) = row
        return RetrievalChunk(
            chunk_id=chunk_id,
            document_id=document_id,
            chunk_type=ChunkType(chunk_type),
            parent_record_id=source_record_id,
            title=title,
            text=content,
            source=(
                SourceReference.model_validate(source)
                if source is not None
                else SourceReference(
                    document_id=document_id,
                    physical_page=physical_page,
                    printed_page=printed_page,
                )
            ),
            field_name=field_name,
            metadata=metadata or {},
            review=(
                ReviewMetadata.model_validate(review)
                if review is not None
                else ReviewMetadata(status=ReviewStatus.PENDING)
            ),
        )

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
                review_status, reviewer, reviewed_at, review_notes, load_position
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
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
                    position,
                )
                for position, record in enumerate(records)
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
    def _insert_chunks(
        cursor: Any,
        records: list[RetrievalChunk],
        jsonb: Any,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        # Embed the same title-plus-text document that HybridRetriever indexes.
        vectors = embedding_provider.embed_texts(
            [f"{record.title}\n{record.text}" for record in records]
        )
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
                printed_page, metadata, review_status, embedding_model,
                embedding, source, load_position
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s::vector, %s, %s
            )
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
                    embedding_provider.name,
                    _vector_literal(vector),
                    jsonb(record.source.model_dump(mode="json")),
                    position,
                )
                for position, (record, vector) in enumerate(zip(records, vectors, strict=True))
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


def _vector_literal(vector: Any) -> str:
    """Format a vector in pgvector's text input syntax."""

    return "[" + ",".join(format(float(value), ".9g") for value in vector) + "]"
