from datetime import datetime, timezone
import unittest

from amu_admissions_rag.indexing import RetrievalChunkBuilder
from amu_admissions_rag.models import (
    AppendixCell,
    AppendixRecord,
    AppendixType,
    ChunkType,
    CourseCorpus,
    CourseField,
    CourseRecord,
    CourseTable,
    CourseTableCell,
    DocumentRecord,
    PolicyCorpus,
    ProgramLevel,
    ReviewMetadata,
    ReviewStatus,
    SectionRecord,
    SourceReference,
)
from amu_admissions_rag.storage import PostgresIndexStore


class RetrievalChunkBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = DocumentRecord(
            document_id="amu-guide-2026-27",
            filename="guide.pdf",
            academic_year="2026-27",
            sha256="a" * 64,
            total_pages=187,
        )
        self.source = SourceReference(
            document_id=self.document.document_id,
            physical_page=94,
            printed_page="B.25",
            section="Faculty of Science",
        )
        self.approved = ReviewMetadata(
            status=ReviewStatus.APPROVED,
            reviewer="reviewer@example.com",
            reviewed_at=datetime(2026, 10, 7, tzinfo=timezone.utc),
        )
        self.course = CourseRecord(
            record_id="amu-guide-2026-27:94:mca",
            document_id=self.document.document_id,
            course_name="Master of Computer Science and Applications (MCA)",
            course_code="CAMSA",
            program_level=ProgramLevel.POSTGRADUATE,
            faculty="Faculty of Science",
            source=self.source,
            fields=[
                CourseField(
                    name="qualifying_examination",
                    label="Qualifying Examination",
                    value="Applicants require Mathematics and at least 55% marks.",
                    source=self.source,
                )
            ],
            tables=[
                CourseTable(
                    name="course_details",
                    headers=["duration", "intake"],
                    rows=[
                        {
                            "duration": CourseTableCell(text="4 Semesters"),
                            "intake": CourseTableCell(text="60+6"),
                        }
                    ],
                    source=self.source,
                )
            ],
            review=self.approved,
        )
        self.section = SectionRecord(
            record_id="amu-guide-2026-27:policy:31:age",
            document_id=self.document.document_id,
            heading="Maximum Age Limit",
            text="Age is reckoned on 01 July of the admission year.",
            source=self.source,
            review=self.approved,
        )
        self.appendix = AppendixRecord(
            record_id="amu-guide-2026-27:test:156:mca",
            document_id=self.document.document_id,
            appendix_type=AppendixType.TEST_SCHEDULE,
            serial_number="87",
            course_name="M.C.A.",
            course_code="CAMSA",
            category="T",
            programme_group="POSTGRADUATE PROGRAMMES",
            faculty="Faculty of Science",
            values={
                "date_or_method": AppendixCell(
                    text="03-06-2026",
                    source=self.source,
                )
            },
            source=self.source,
            review=self.approved,
        )

    def test_course_field_chunk_is_self_contained_and_linked(self) -> None:
        corpus = self._build()
        chunk = next(
            item
            for item in corpus.chunks
            if item.chunk_type is ChunkType.COURSE_FIELD
        )

        self.assertEqual(chunk.parent_record_id, self.course.record_id)
        self.assertIn("Master of Computer Science and Applications (MCA)", chunk.text)
        self.assertIn("Course Code: CAMSA", chunk.text)
        self.assertIn("Field: Qualifying Examination", chunk.text)
        self.assertIn("at least 55% marks", chunk.text)
        self.assertEqual(chunk.field_name, "qualifying_examination")

    def test_course_profile_contains_full_fields_and_table_summary(self) -> None:
        corpus = self._build()
        profile = next(
            item
            for item in corpus.chunks
            if item.chunk_type is ChunkType.COURSE_OVERVIEW
        )

        self.assertIn("Record Type: Course Profile", profile.text)
        self.assertIn(
            "Qualifying Examination: Applicants require Mathematics",
            profile.text,
        )
        self.assertIn("Duration=4 Semesters", profile.text)
        self.assertIn("Intake=60+6", profile.text)
        self.assertEqual(profile.metadata["retrieval_role"], "course_discovery")

    def test_course_table_row_is_its_own_self_contained_chunk(self) -> None:
        corpus = self._build()
        chunk = next(
            item
            for item in corpus.chunks
            if item.chunk_type is ChunkType.COURSE_TABLE_ROW
        )

        self.assertIn("Course: Master of Computer Science", chunk.text)
        self.assertIn("Duration: 4 Semesters", chunk.text)
        self.assertIn("Intake: 60+6", chunk.text)
        self.assertEqual(chunk.parent_record_id, self.course.record_id)

    def test_policy_and_appendix_chunks_are_independently_searchable(self) -> None:
        corpus = self._build()
        policy = next(
            item
            for item in corpus.chunks
            if item.chunk_type is ChunkType.POLICY_SECTION
        )
        appendix = next(
            item
            for item in corpus.chunks
            if item.chunk_type is ChunkType.APPENDIX_ROW
        )

        self.assertIn("Section: Maximum Age Limit", policy.text)
        self.assertIn("Course: M.C.A.", appendix.text)
        self.assertIn("Date Or Method: 03-06-2026", appendix.text)

    def test_default_build_excludes_pending_records(self) -> None:
        pending_course = self.course.model_copy(
            update={"review": ReviewMetadata()}
        )
        course_corpus = CourseCorpus(
            document=self.document,
            courses=[pending_course],
        )
        policy_corpus = PolicyCorpus(
            document=self.document,
            sections=[],
            appendix_rows=[],
        )

        corpus = RetrievalChunkBuilder().build(course_corpus, policy_corpus)

        self.assertEqual(corpus.chunks, [])

    def test_preview_can_include_pending_but_never_rejected_records(self) -> None:
        pending_course = self.course.model_copy(
            update={"review": ReviewMetadata()}
        )
        rejected_section = self.section.model_copy(
            update={
                "review": ReviewMetadata(
                    status=ReviewStatus.REJECTED,
                    reviewer="reviewer@example.com",
                    reviewed_at=datetime(2026, 10, 7, tzinfo=timezone.utc),
                )
            }
        )
        course_corpus = CourseCorpus(
            document=self.document,
            courses=[pending_course],
        )
        policy_corpus = PolicyCorpus(
            document=self.document,
            sections=[rejected_section],
            appendix_rows=[],
        )

        corpus = RetrievalChunkBuilder().build(
            course_corpus,
            policy_corpus,
            include_pending=True,
        )

        self.assertEqual(len(corpus.chunks), 3)
        self.assertTrue(
            all(chunk.review.status is ReviewStatus.PENDING for chunk in corpus.chunks)
        )

    def test_build_rejects_mismatched_documents(self) -> None:
        other_document = self.document.model_copy(update={"document_id": "other"})
        policy_corpus = PolicyCorpus(
            document=other_document,
            sections=[],
            appendix_rows=[],
        )

        with self.assertRaises(ValueError):
            RetrievalChunkBuilder().build(
                CourseCorpus(document=self.document, courses=[]),
                policy_corpus,
            )

    def test_postgres_loader_refuses_empty_approved_corpus_before_connecting(self) -> None:
        pending_course = self.course.model_copy(
            update={"review": ReviewMetadata()}
        )
        store = PostgresIndexStore("postgresql://unused")

        with self.assertRaisesRegex(ValueError, "no approved chunks"):
            store.replace_approved_corpus(
                CourseCorpus(document=self.document, courses=[pending_course]),
                PolicyCorpus(
                    document=self.document,
                    sections=[],
                    appendix_rows=[],
                ),
            )

    def test_postgres_loader_persists_parent_links_only_for_course_chunks(self) -> None:
        connection = _FakeConnection()
        store = PostgresIndexStore("postgresql://unused")
        store._driver = lambda: (_FakePsycopg(connection), lambda value: value)

        count = store.replace_approved_corpus(
            CourseCorpus(document=self.document, courses=[self.course]),
            PolicyCorpus(
                document=self.document,
                sections=[self.section],
                appendix_rows=[self.appendix],
            ),
        )

        self.assertEqual(count, 5)
        chunk_rows = next(
            rows
            for query, rows in connection.cursor_instance.batches
            if "INSERT INTO retrieval_chunks" in query
        )
        course_rows = [row for row in chunk_rows if row[2].startswith("course_")]
        independent_rows = [
            row for row in chunk_rows if not row[2].startswith("course_")
        ]
        self.assertTrue(all(row[4] == self.course.record_id for row in course_rows))
        self.assertTrue(all(row[4] is None for row in independent_rows))

    def _build(self):
        return RetrievalChunkBuilder().build(
            CourseCorpus(document=self.document, courses=[self.course]),
            PolicyCorpus(
                document=self.document,
                sections=[self.section],
                appendix_rows=[self.appendix],
            ),
        )
class _FakeCursor:
    def __init__(self) -> None:
        self.executions = []
        self.batches = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, query, params=None) -> None:
        self.executions.append((query, params))

    def executemany(self, query, params) -> None:
        self.batches.append((query, params))


class _FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = _FakeCursor()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def transaction(self):
        return self

    def cursor(self):
        return self.cursor_instance


class _FakePsycopg:
    def __init__(self, connection) -> None:
        self.connection = connection

    def connect(self, database_url):
        return self.connection


if __name__ == "__main__":
    unittest.main()
