"""Round-trip tests against a real PostgreSQL + pgvector database.

Skipped unless AMU_RAG_TEST_DATABASE_URL points at a disposable database, e.g.
the ``amu_test`` database described in docs/DOCKER.md. Never point it at the
application database: the tests create and delete their own document.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
import unittest

from amu_admissions_rag.indexing import RetrievalChunkBuilder
from amu_admissions_rag.models import (
    AppendixCell,
    AppendixRecord,
    AppendixType,
    CourseCorpus,
    CourseField,
    CourseRecord,
    DocumentRecord,
    PolicyCorpus,
    ProgramLevel,
    ReviewMetadata,
    ReviewStatus,
    SectionRecord,
    SourceReference,
)
from amu_admissions_rag.storage import IngestionRun, PostgresIndexStore

DATABASE_URL = os.environ.get("AMU_RAG_TEST_DATABASE_URL", "")
SQL_DIR = Path(__file__).resolve().parents[1] / "sql"
DOCUMENT_ID = "integration-test-guide"


def _review(status: ReviewStatus) -> ReviewMetadata:
    if status is ReviewStatus.PENDING:
        return ReviewMetadata()
    return ReviewMetadata(
        status=status,
        reviewer="integration-test",
        reviewed_at=datetime(2026, 10, 7, tzinfo=timezone.utc),
        notes="test fixture",
    )


def _corpora() -> tuple[CourseCorpus, PolicyCorpus]:
    document = DocumentRecord(
        document_id=DOCUMENT_ID,
        filename="integration.pdf",
        academic_year="2026-27",
        sha256="c" * 64,
        total_pages=10,
    )

    def source(page: int) -> SourceReference:
        return SourceReference(
            document_id=DOCUMENT_ID, physical_page=page, printed_page=f"T.{page}"
        )

    def course(record_id: str, name: str, status: ReviewStatus) -> CourseRecord:
        return CourseRecord(
            record_id=record_id,
            document_id=DOCUMENT_ID,
            course_name=name,
            program_level=ProgramLevel.POSTGRADUATE,
            faculty="Faculty of Testing",
            source=source(1),
            fields=[
                CourseField(
                    name="age_limit", label="Age Limit", value="Thirty years.", source=source(1)
                )
            ],
            review=_review(status),
        )

    courses = CourseCorpus(
        document=document,
        courses=[
            course("it:mca", "Master of Computer Science and Applications (MCA)",
                   ReviewStatus.APPROVED),
            course("it:pending", "Pending Course", ReviewStatus.PENDING),
            course("it:rejected", "Rejected Course", ReviewStatus.REJECTED),
        ],
    )
    policies = PolicyCorpus(
        document=document,
        sections=[
            SectionRecord(
                record_id="it:refunds",
                document_id=DOCUMENT_ID,
                heading="Refunds",
                text="Fees are refunded within seven days.",
                source=source(2).model_copy(update={"section": "Refunds"}),
                review=_review(ReviewStatus.APPROVED),
            )
        ],
        appendix_rows=[
            AppendixRecord(
                record_id="it:fee",
                document_id=DOCUMENT_ID,
                appendix_type=AppendixType.FEE_SUMMARY,
                serial_number="1",
                course_name="Master of Computer Science and Applications (MCA)",
                source=source(3),
                values={"admission_fee": AppendixCell(text="Rs. 100", source=source(3))},
                review=_review(ReviewStatus.APPROVED),
            )
        ],
    )
    return courses, policies


@unittest.skipUnless(DATABASE_URL, "AMU_RAG_TEST_DATABASE_URL is not set")
class PostgresIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.store = PostgresIndexStore(DATABASE_URL)
        cls.store.apply_migrations(SQL_DIR)

    def tearDown(self) -> None:
        import psycopg

        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute("DELETE FROM documents WHERE document_id = %s", (DOCUMENT_ID,))

    def test_migrations_are_idempotent(self) -> None:
        self.assertEqual(self.store.apply_migrations(SQL_DIR), [])

    def test_approved_corpus_round_trips_losslessly(self) -> None:
        courses, policies = _corpora()
        expected_index = RetrievalChunkBuilder().build(courses, policies)

        loaded = self.store.replace_approved_corpus(
            courses,
            policies,
            ingestion=IngestionRun(fingerprint="d" * 64, pipeline_version="test"),
        )
        index, stored_courses = self.store.load_approved_corpora(DOCUMENT_ID)

        self.assertEqual(loaded, 3)
        self.assertEqual(index, expected_index)
        self.assertEqual([c.record_id for c in stored_courses.courses], ["it:mca"])
        self.assertEqual(stored_courses.courses[0], courses.courses[0])
        self.assertEqual(self.store.latest_ingestion_fingerprint(DOCUMENT_ID), "d" * 64)

    def test_reload_replaces_previous_corpus_atomically(self) -> None:
        courses, policies = _corpora()
        self.store.replace_approved_corpus(courses, policies)
        empty_policies = policies.model_copy(update={"sections": [], "appendix_rows": []})

        self.store.replace_approved_corpus(courses, empty_policies)
        index, _ = self.store.load_approved_corpora(DOCUMENT_ID)

        self.assertEqual([chunk.chunk_id for chunk in index.chunks], ["it:mca:overview"])

    def test_embeddings_are_stored_for_sql_hybrid_search(self) -> None:
        import psycopg

        courses, policies = _corpora()
        self.store.replace_approved_corpus(courses, policies)
        with psycopg.connect(DATABASE_URL) as connection:
            dims, missing = connection.execute(
                """
                SELECT min(vector_dims(embedding)), count(*) FILTER (WHERE embedding IS NULL)
                FROM retrieval_chunks WHERE document_id = %s
                """,
                (DOCUMENT_ID,),
            ).fetchone()
            top = connection.execute(
                "SELECT chunk_id FROM hybrid_search_chunks(%s, NULL, 1)",
                ("refunded seven days",),
            ).fetchone()

        self.assertEqual((dims, missing), (1024, 0))
        self.assertEqual(top[0], "it:refunds:chunk")

    def test_database_rejects_unapproved_chunks(self) -> None:
        import psycopg

        courses, policies = _corpora()
        self.store.replace_approved_corpus(courses, policies)
        with psycopg.connect(DATABASE_URL) as connection:
            with self.assertRaises(psycopg.errors.CheckViolation):
                connection.execute(
                    "UPDATE retrieval_chunks SET review_status = 'pending' "
                    "WHERE document_id = %s",
                    (DOCUMENT_ID,),
                )


if __name__ == "__main__":
    unittest.main()
