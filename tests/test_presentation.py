import unittest

from amu_admissions_rag.presentation import context_preview, link_answer_citations


class PresentationTests(unittest.TestCase):
    def test_only_valid_citations_become_links(self) -> None:
        rendered = link_answer_citations(
            "Supported [SOURCE 1]. Unknown [SOURCE 3].",
            [1],
        )
        self.assertIn("[1](#source-1)", rendered)
        self.assertIn("[SOURCE 3]", rendered)

    def test_unicode_citation_becomes_the_same_source_link(self) -> None:
        rendered = link_answer_citations(
            "Requirement 【SOURCE 1】.",
            [1],
        )

        self.assertEqual(rendered, "Requirement [1](#source-1).")

    def test_context_preview_preserves_short_text(self) -> None:
        self.assertEqual(context_preview("Course: MCA\nAge: 27"), "Course: MCA Age: 27")

    def test_context_preview_truncates_on_word_boundary(self) -> None:
        preview = context_preview("one two three four", limit=13)
        self.assertEqual(preview, "one two…")


if __name__ == "__main__":
    unittest.main()
