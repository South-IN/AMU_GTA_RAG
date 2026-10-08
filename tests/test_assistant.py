import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from amu_admissions_rag.assistant import (
    AdmissionsAssistant,
    cited_source_numbers,
    should_discover_courses,
)
from amu_admissions_rag.models import (
    ChunkType,
    QueryAnalysis,
    QueryIntent,
    RetrievalChunk,
    RetrievalHit,
    ReviewMetadata,
    ReviewStatus,
    SourceReference,
)


def _hit(
    *,
    chunk_id: str = "guide:1:course",
    chunk_type: ChunkType = ChunkType.COURSE_OVERVIEW,
    title: str = "Example Course - Complete Course Information",
) -> RetrievalHit:
    return RetrievalHit(
        chunk=RetrievalChunk(
            chunk_id=chunk_id,
            document_id="guide",
            chunk_type=chunk_type,
            parent_record_id="course:1",
            title=title,
            text="Course: Example\nQualifying Examination: Example requirement.",
            source=SourceReference(
                document_id="guide",
                physical_page=10,
                printed_page="A.1",
            ),
            review=ReviewMetadata(
                status=ReviewStatus.APPROVED,
                reviewer="reviewer",
                reviewed_at="2026-10-07T00:00:00Z",
            ),
        ),
        fused_score=0.1,
        lexical_score=1.0,
        vector_score=0.5,
    )


def _analysis(query: str) -> QueryAnalysis:
    return QueryAnalysis(
        original_query=query,
        expanded_query=query,
        intents=[QueryIntent.GENERAL],
    )


class AssistantTests(unittest.TestCase):
    def test_citation_parser_separates_invalid_sources(self) -> None:
        valid, invalid = cited_source_numbers(
            "Fact [SOURCE 1]. Duplicate [SOURCE 1]. Wrong [SOURCE 4].",
            2,
        )
        self.assertEqual(valid, [1])
        self.assertEqual(invalid, [4])

    def test_citation_parser_accepts_unicode_source_brackets(self) -> None:
        valid, invalid = cited_source_numbers(
            "Supported 【SOURCE 1】 and unavailable 【 SOURCE 3 】.",
            2,
        )

        self.assertEqual(valid, [1])
        self.assertEqual(invalid, [3])

    def test_discovery_routing_requires_course_suggestion_language(self) -> None:
        self.assertTrue(
            should_discover_courses(
                "I completed B.Sc. Computer Science. Which postgraduate courses may fit?"
            )
        )
        self.assertFalse(should_discover_courses("What is the MCA age limit?"))

    def test_missing_citation_triggers_one_repair(self) -> None:
        query = "What is required?"
        hit = _hit()
        retriever = Mock()
        retriever.search.return_value = SimpleNamespace(
            query=_analysis(query),
            hits=[hit],
        )
        generator = Mock()
        generator.model = "test-model"
        generator.generate.return_value = "The requirement is Example."
        generator.repair_citations.return_value = "The requirement is Example [SOURCE 1]."

        reply = AdmissionsAssistant(retriever, generator).ask(query)

        generator.repair_citations.assert_called_once()
        self.assertEqual(reply.cited_source_numbers, [1])
        self.assertTrue(reply.citation_repair_attempted)
        self.assertIsNone(reply.citation_warning)

    def test_discovery_overclaim_triggers_eligibility_repair(self) -> None:
        query = "Which courses may fit?"
        hit = _hit()
        retriever = Mock()
        retriever.discover_courses.return_value = SimpleNamespace(
            query=_analysis(query),
            candidates=[SimpleNamespace(profile=hit)],
        )
        retriever.search.return_value = SimpleNamespace(
            query=_analysis(query),
            hits=[],
        )
        generator = Mock()
        generator.model = "test-model"
        generator.generate.return_value = "You qualify for this course [SOURCE 1]."
        generator.repair_eligibility_claims.return_value = (
            "This is a potential match; your marks remain unverified [SOURCE 1]."
        )

        reply = AdmissionsAssistant(retriever, generator).ask(
            query,
            discover_courses=True,
        )

        generator.repair_eligibility_claims.assert_called_once()
        self.assertTrue(reply.eligibility_repair_attempted)
        self.assertIn("potential match", reply.answer)

    def test_relevant_policy_hits_are_added_and_deduplicated(self) -> None:
        query = "Am I eligible?"
        course_hit = _hit()
        policy_hit = _hit(
            chunk_id="guide:policy:1",
            chunk_type=ChunkType.POLICY_SECTION,
            title="Important eligibility rules",
        )
        retriever = Mock()
        retriever.search.side_effect = [
            SimpleNamespace(query=_analysis(query), hits=[course_hit]),
            SimpleNamespace(query=_analysis(query), hits=[course_hit, policy_hit]),
        ]
        generator = Mock()
        generator.model = "test-model"
        generator.generate.return_value = "Supported [SOURCE 1] [SOURCE 2]."

        reply = AdmissionsAssistant(retriever, generator).ask(query)

        self.assertEqual(
            [hit.chunk.chunk_id for hit in reply.hits],
            [course_hit.chunk.chunk_id, policy_hit.chunk.chunk_id],
        )
        self.assertIn("Evidence type: Guide-wide admissions policy", reply.context)
        self.assertEqual(retriever.search.call_args_list[1].kwargs["limit"], 2)
        self.assertEqual(
            retriever.search.call_args_list[1].kwargs["chunk_types"],
            {ChunkType.POLICY_SECTION},
        )

    def test_valid_citation_does_not_trigger_repair(self) -> None:
        query = "What is required?"
        hit = _hit()
        retriever = Mock()
        retriever.search.return_value = SimpleNamespace(
            query=_analysis(query),
            hits=[hit],
        )
        generator = Mock()
        generator.model = "test-model"
        generator.generate.return_value = "The requirement is Example [SOURCE 1]."
        generator.repair_eligibility_claims = Mock()

        reply = AdmissionsAssistant(retriever, generator).ask(query)

        generator.repair_citations.assert_not_called()
        generator.repair_eligibility_claims.assert_not_called()
        self.assertFalse(reply.citation_repair_attempted)


if __name__ == "__main__":
    unittest.main()
