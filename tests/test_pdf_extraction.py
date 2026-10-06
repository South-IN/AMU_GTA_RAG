import unittest

from amu_admissions_rag.config import AppPaths
from amu_admissions_rag.extraction import PdfExtractor, parse_page_spec


class PageSpecTests(unittest.TestCase):
    def test_parse_page_ranges(self) -> None:
        self.assertEqual(parse_page_spec("1,54-56,128", 187), [1, 54, 55, 56, 128])

    def test_reject_descending_range(self) -> None:
        with self.assertRaises(ValueError):
            parse_page_spec("5-2")


class PdfExtractorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        paths = AppPaths.from_package()
        cls.extractor = PdfExtractor(paths.source_pdf)
        cls.document = cls.extractor.document_record()
        cls.bundle = cls.extractor.extract_pages([1, 54, 128])

    def test_document_metadata(self) -> None:
        self.assertEqual(self.document.total_pages, 187)
        self.assertEqual(len(self.document.sha256), 64)

    def test_cover_text_is_extracted(self) -> None:
        cover = self.bundle.pages[0]

        self.assertIn("Guide to Admissions", cover.text)
        self.assertGreater(len(cover.lines), 0)

    def test_course_page_has_printed_label_and_tables(self) -> None:
        course_page = self.bundle.pages[1]

        self.assertEqual(course_page.printed_page, "A.1")
        self.assertIn("B.Sc. (Hons.) Agriculture", course_page.text)
        self.assertGreaterEqual(len(course_page.tables), 2)

    def test_appendix_page_preserves_landscape_layout(self) -> None:
        appendix_page = self.bundle.pages[2]

        self.assertEqual(appendix_page.printed_page, "J.1")
        self.assertGreater(appendix_page.width, appendix_page.height)
        self.assertGreaterEqual(len(appendix_page.tables), 1)


if __name__ == "__main__":
    unittest.main()

