import unittest

from amu_admissions_rag.generation_eval_cli import EVALUATION_CASES, _markdown_case


class GenerationEvaluationTests(unittest.TestCase):
    def test_evaluation_set_is_varied_and_bounded(self) -> None:
        self.assertGreaterEqual(len(EVALUATION_CASES), 5)
        self.assertLessEqual(len(EVALUATION_CASES), 10)
        self.assertTrue(any(case.discover_courses for case in EVALUATION_CASES))
        self.assertTrue(any("M.C.A." in case.query for case in EVALUATION_CASES))
        self.assertTrue(any("B.A.LL.B." in case.query for case in EVALUATION_CASES))

    def test_markdown_includes_auditable_fields(self) -> None:
        rendered = _markdown_case(
            1,
            EVALUATION_CASES[0],
            "expanded question",
            "[SOURCE 1]\ncontext",
            "answer [SOURCE 1]",
            [],
        )
        self.assertIn("Expanded query", rendered)
        self.assertIn("Retrieved context", rendered)
        self.assertIn("LLM answer", rendered)
        self.assertIn("answer [SOURCE 1]", rendered)


if __name__ == "__main__":
    unittest.main()
