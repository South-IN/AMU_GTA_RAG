import json
import unittest
from pathlib import Path

from amu_admissions_rag.models import QueryIntent
from amu_admissions_rag.query_processing import (
    QueryProcessor,
    course_name_expansions,
    unrecognised_abbreviations,
)

COURSE_NAMES_FIXTURE = Path(__file__).parent / "fixtures" / "guide-2026-27-course-names.json"


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

    def test_common_word_be_is_not_expanded_as_engineering_degree(self) -> None:
        query = "Which courses could I be eligible for?"

        self.assertEqual(self.processor.expand(query), query)
        self.assertEqual(
            self.processor.expand("Can a B.E. graduate apply?"),
            "Can a Bachelor of Engineering graduate apply?",
        )

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

    def test_degree_needed_is_an_eligibility_intent(self) -> None:
        analysis = self.processor.analyze("What degree do I need for MSW?")

        self.assertIn(QueryIntent.ELIGIBILITY, analysis.intents)
        self.assertEqual(analysis.preferred_fields, ["qualifying_examination"])

    def test_can_i_do_is_eligibility_but_academic_marks_are_not_test_details(self) -> None:
        analysis = self.processor.analyze("I have 60% marks. Can I do MCA?")

        self.assertIn(QueryIntent.ELIGIBILITY, analysis.intents)
        self.assertNotIn(QueryIntent.TEST_DETAILS, analysis.intents)

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
        self.assertEqual(
            course_name_expansions("Master of Social Work (M.S.W.)"),
            ["Master of Social Work"],
        )
        self.assertEqual(
            course_name_expansions("B.Lib.I.Sc."),
            ["Bachelor of Library and Information Science"],
        )
        self.assertEqual(
            course_name_expansions("P.G. Diploma in Computer Programming (PGDCP)"),
            ["Post Graduate Diploma in Computer Programming"],
        )

    def test_guide_course_name_abbreviations_are_recognised(self) -> None:
        names = json.loads(COURSE_NAMES_FIXTURE.read_text(encoding="utf-8"))["course_names"]

        unrecognised = {
            name: missing for name in names if (missing := unrecognised_abbreviations(name))
        }

        self.assertGreater(len(names), 150)
        self.assertEqual(unrecognised, {})

    def test_unrecognised_abbreviation_detection(self) -> None:
        self.assertEqual(unrecognised_abbreviations("D.Litt. in Physics"), ["D.Litt."])
        self.assertEqual(unrecognised_abbreviations("Remote Sensing & GIS"), [])
        self.assertEqual(unrecognised_abbreviations("M.Sc. Physics (MCA)"), [])

    def test_guide_spellings_expand(self) -> None:
        cases = {
            "B.Lib.I.Sc. intake": "Bachelor of Library and Information Science intake",
            "M.Lib.I.Sc. intake": "Master of Library and Information Science intake",
            "B.P.Ed. fees": "Bachelor of Physical Education fees",
            "M.P.Ed. fees": "Master of Physical Education fees",
            "M. Arch. seats": "Master of Architecture seats",
            "M.Plan-Urban seats": "Master of Planning-Urban seats",
            "PGDCP seats": "Post Graduate Diploma in Computer Programming seats",
            "P.G. Diploma in Linguistics": "Post Graduate Diploma in Linguistics",
            "PG Diploma in Linguistics": "Post Graduate Diploma in Linguistics",
            "BPT eligibility": "Bachelor of Physiotherapy eligibility",
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                self.assertEqual(self.processor.expand(query), expected)

    def test_word_like_aliases_need_capitals_or_periods(self) -> None:
        for query in [
            "Is there a hostel bed for girls?",
            "I want to study med",
            "Can I get admission, ma'am?",
            "Are the exams in March?",
            "Which courses could I be eligible for?",
        ]:
            with self.subTest(query=query):
                self.assertEqual(self.processor.expand(query), query)
        for query, expected in {
            "BEd fees": "Bachelor of Education fees",
            "b.ed fees": "Bachelor of Education fees",
            "B Ed fees": "Bachelor of Education fees",
            "MED seats": "Master of Education seats",
            "m.a. english": "Master of Arts english",
            "MA English": "Master of Arts English",
            "MArch seats": "Master of Architecture seats",
        }.items():
            with self.subTest(query=query):
                self.assertEqual(self.processor.expand(query), expected)


if __name__ == "__main__":
    unittest.main()
