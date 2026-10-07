import unittest

from amu_admissions_rag.models import QueryIntent
from amu_admissions_rag.query_processing import (
    QueryProcessor,
    course_name_expansions,
)


class QueryProcessorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.processor = QueryProcessor()

    def test_mca_punctuation_variants_expand_to_same_course_name(self) -> None:
        variants = ("MCA", "mca", "M.C.A", "M.C.A.", "M.CA", "M C A")

        expanded = {
            self.processor.expand(f"Am I eligible for {variant}?")
            for variant in variants
        }

        self.assertEqual(
            expanded,
            {
                "Am I eligible for "
                "Master of Computer Science and Applications?"
            },
        )

    def test_expansion_preserves_non_alias_case_whitespace_and_punctuation(self) -> None:
        query = "Can I apply for M.C.A. at AMU, Aligarh?"

        expanded = self.processor.expand(query)

        self.assertEqual(
            expanded,
            "Can I apply for Master of Computer Science and Applications "
            "at AMU, Aligarh?",
        )

    def test_multiple_course_aliases_are_expanded(self) -> None:
        expanded = self.processor.expand("Compare B.Tech and MTech eligibility")

        self.assertEqual(
            expanded,
            "Compare Bachelor of Technology and Master of Technology eligibility",
        )

    def test_aliases_are_not_matched_inside_other_words(self) -> None:
        query = "Tell me about chemical engineering"

        self.assertEqual(self.processor.expand(query), query)

    def test_eligibility_intent_prefers_qualifying_examination(self) -> None:
        analysis = self.processor.analyze("Am I eligible for MCA?")

        self.assertIn(QueryIntent.ELIGIBILITY, analysis.intents)
        self.assertEqual(analysis.preferred_fields, ["qualifying_examination"])
        self.assertEqual(analysis.aliases[0].matched_text, "MCA")

    def test_multi_intent_query_retains_each_preferred_field(self) -> None:
        analysis = self.processor.analyze(
            "What is the age limit and test date for M.C.A.?"
        )

        self.assertIn(QueryIntent.AGE_LIMIT, analysis.intents)
        self.assertIn(QueryIntent.TEST_SCHEDULE, analysis.intents)
        self.assertEqual(
            analysis.preferred_fields,
            ["age_limit", "test_schedule"],
        )

    def test_apply_for_is_an_eligibility_intent(self) -> None:
        analysis = self.processor.analyze("Can a B.Com graduate apply for MCA?")

        self.assertIn(QueryIntent.ELIGIBILITY, analysis.intents)
        self.assertEqual(analysis.preferred_fields, ["qualifying_examination"])

    def test_subject_requirement_is_an_eligibility_intent(self) -> None:
        analysis = self.processor.analyze(
            "Does chemical engineering require maths?"
        )

        self.assertIn(QueryIntent.ELIGIBILITY, analysis.intents)

    def test_how_long_is_a_duration_intent(self) -> None:
        analysis = self.processor.analyze("How long is B.E.?")

        self.assertIn(QueryIntent.DURATION, analysis.intents)
        self.assertEqual(analysis.preferred_fields, ["course_details"])

    def test_query_without_known_intent_is_general(self) -> None:
        analysis = self.processor.analyze("Tell me about MBA")

        self.assertEqual(analysis.intents, [QueryIntent.GENERAL])
        self.assertEqual(
            analysis.expanded_query,
            "Tell me about Master of Business Administration",
        )

    def test_empty_query_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.processor.analyze("   ")

    def test_abbreviated_course_name_gets_matching_expansion_for_indexing(self) -> None:
        self.assertEqual(
            course_name_expansions("M.B.B.S."),
            ["Bachelor of Medicine and Bachelor of Surgery"],
        )
        self.assertEqual(
            course_name_expansions("B.A.LL.B."),
            ["Bachelor of Arts and Bachelor of Laws"],
        )


if __name__ == "__main__":
    unittest.main()
