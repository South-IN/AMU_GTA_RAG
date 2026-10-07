import unittest
from datetime import datetime, timezone

import numpy as np

from amu_admissions_rag.indexing import RetrievalChunkBuilder
from amu_admissions_rag.models import (
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
    SourceReference,
)
from amu_admissions_rag.retrieval import (
    HashingEmbeddingProvider,
    HybridRetriever,
    format_llm_context,
)


class HybridRetrievalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = DocumentRecord(
            document_id="guide",
            filename="guide.pdf",
            academic_year="2026-27",
            sha256="a" * 64,
            total_pages=10,
        )
        approved = ReviewMetadata(
            status=ReviewStatus.APPROVED,
            reviewer="reviewer",
            reviewed_at=datetime(2026, 10, 7, tzinfo=timezone.utc),
        )
        mca_source = SourceReference(
            document_id="guide", physical_page=4, printed_page="A.40"
        )
        mba_source = SourceReference(
            document_id="guide", physical_page=5, printed_page="A.41"
        )
        self.mca = CourseRecord(
            record_id="course:mca",
            document_id="guide",
            course_name="Master of Computer Science and Applications (MCA)",
            program_level=ProgramLevel.POSTGRADUATE,
            faculty="Faculty of Science",
            source=mca_source,
            fields=[
                CourseField(
                    name="qualifying_examination",
                    label="Qualifying Examination",
                    value=(
                        "B.Sc. Computer Science with Mathematics, at least "
                        "16 Mathematics credits and 55% marks."
                    ),
                    source=mca_source,
                ),
                CourseField(
                    name="age_limit",
                    label="Age Limit",
                    value="Not more than 27 years.",
                    source=mca_source,
                ),
            ],
            tables=[
                CourseTable(
                    name="course_details",
                    headers=["branch_name", "intake"],
                    rows=[
                        {
                            "branch_name": CourseTableCell(
                                text="Computer Applications", source=mca_source
                            ),
                            "intake": CourseTableCell(text="40", source=mca_source),
                        },
                        {
                            "branch_name": CourseTableCell(
                                text="Computer Applications (Data Science)",
                                source=mca_source,
                            ),
                            "intake": CourseTableCell(text="20", source=mca_source),
                        },
                    ],
                    source=mca_source,
                )
            ],
            review=approved,
        )
        self.mba = CourseRecord(
            record_id="course:mba",
            document_id="guide",
            course_name="Master of Business Administration (MBA)",
            program_level=ProgramLevel.POSTGRADUATE,
            faculty="Faculty of Management Studies",
            source=mba_source,
            fields=[
                CourseField(
                    name="selection_process",
                    label="Selection Process",
                    value="Selected through an admission test and interview.",
                    source=mba_source,
                )
            ],
            review=approved,
        )
        self.bsc = CourseRecord(
            record_id="course:bsc",
            document_id="guide",
            course_name="B.Sc. (Hons.) Computer Science",
            program_level=ProgramLevel.UNDERGRADUATE,
            faculty="Faculty of Science",
            source=mba_source,
            fields=[
                CourseField(
                    name="qualifying_examination",
                    label="Qualifying Examination",
                    value="Senior Secondary School Certificate with Mathematics.",
                    source=mba_source,
                )
            ],
            review=approved,
        )
        course_corpus = CourseCorpus(
            document=self.document,
            courses=[self.mca, self.mba, self.bsc],
        )
        policy_corpus = PolicyCorpus(
            document=self.document,
            sections=[],
            appendix_rows=[],
        )
        index_corpus = RetrievalChunkBuilder().build(course_corpus, policy_corpus)
        self.retriever = HybridRetriever(index_corpus, course_corpus)

    def test_hashing_embeddings_are_deterministic_and_normalized(self) -> None:
        provider = HashingEmbeddingProvider(dimensions=128)

        first = provider.embed_texts(["MCA eligibility"])
        second = provider.embed_texts(["MCA eligibility"])

        np.testing.assert_array_equal(first, second)
        self.assertAlmostEqual(float(np.linalg.norm(first[0])), 1.0, places=6)

    def test_query_retrieves_complete_course_information(self) -> None:
        response = self.retriever.search("Am I eligible for M.C.A.?", limit=3)

        self.assertEqual(
            response.query.expanded_query,
            "Am I eligible for Master of Computer Science and Applications?",
        )
        self.assertEqual(response.hits[0].chunk.parent_record_id, self.mca.record_id)
        self.assertIn("Qualifying Examination:", response.hits[0].chunk.text)
        self.assertIn("Age Limit:", response.hits[0].chunk.text)
        self.assertIn("Course Details:", response.hits[0].chunk.text)
        self.assertGreater(response.hits[0].course_match_boost, 0)

    def test_retrieved_course_retains_source_and_parent(self) -> None:
        response = self.retriever.search("What is the MCA age limit?", limit=2)

        self.assertIn(self.mca.record_id, response.course_parents)
        parent = response.course_parents[self.mca.record_id]
        self.assertEqual(len(parent.fields), 2)
        self.assertEqual(response.hits[0].chunk.source.printed_page, "A.40")

    def test_selection_query_finds_a_different_course(self) -> None:
        response = self.retriever.search("How does MBA selection work?", limit=1)

        self.assertEqual(response.hits[0].chunk.parent_record_id, self.mba.record_id)
        self.assertIn("Selection Process:", response.hits[0].chunk.text)
        self.assertIn("admission test and interview", response.hits[0].chunk.text)

    def test_course_chunk_retains_all_similar_table_rows(self) -> None:
        response = self.retriever.search(
            "How many Computer Applications seats are there?",
            limit=2,
        )

        self.assertIn("Branch Name=Computer Applications; Intake=40", response.hits[0].chunk.text)
        self.assertIn(
            "Branch Name=Computer Applications (Data Science); Intake=20",
            response.hits[0].chunk.text,
        )

    def test_course_discovery_ranks_profiles_and_attaches_field_evidence(self) -> None:
        response = self.retriever.discover_courses(
            "I completed B.Sc. Computer Science. Which courses am I eligible for?",
            limit=2,
        )

        self.assertEqual(response.candidates[0].course.record_id, self.mca.record_id)
        self.assertGreater(response.candidates[0].program_level_boost, 0)
        self.assertIn(
            "16 Mathematics credits",
            response.candidates[0].profile.chunk.text,
        )
        self.assertEqual(
            response.candidates[0].evidence[0].chunk.chunk_id,
            response.candidates[0].profile.chunk.chunk_id,
        )

    def test_named_course_discovery_exposes_numeric_requirement(self) -> None:
        response = self.retriever.discover_courses(
            "I have 12 credits in Mathematics. Can I do MCA?",
            limit=1,
        )

        self.assertEqual(response.query.preferred_fields, ["qualifying_examination"])
        self.assertEqual(response.candidates[0].course.record_id, self.mca.record_id)
        self.assertIn(
            "16 Mathematics credits",
            response.candidates[0].evidence[0].chunk.text,
        )

    def test_llm_context_contains_information_and_citation_not_scores(self) -> None:
        response = self.retriever.search("Can I do MCA?", limit=1)

        context = format_llm_context(response.hits)

        self.assertIn("[SOURCE 1]", context)
        self.assertIn("16 Mathematics credits", context)
        self.assertIn("page A.40", context)
        self.assertNotIn("fused_score", context)


if __name__ == "__main__":
    unittest.main()
