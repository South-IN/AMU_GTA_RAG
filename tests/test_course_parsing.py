import unittest

from amu_admissions_rag.config import AppPaths
from amu_admissions_rag.extraction import PdfExtractor
from amu_admissions_rag.models import ReviewStatus
from amu_admissions_rag.parsing import CourseParser


class CourseParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        paths = AppPaths.from_package()
        extractor = PdfExtractor(paths.source_pdf)
        cls.undergraduate = CourseParser().parse(extractor.extract_pages([54]))
        cls.engineering = CourseParser().parse(
            extractor.extract_pages([80]),
            initial_faculty="Faculty of Engineering & Technology",
        )

    def test_standard_course_card(self) -> None:
        agriculture = self.undergraduate.courses[0]

        self.assertIn("B.Sc. (Hons.) Agriculture", agriculture.course_name)
        self.assertEqual(agriculture.course_code, "AGBGA")
        self.assertEqual(agriculture.source.printed_page, "A.1")
        self.assertEqual(agriculture.review.status, ReviewStatus.PENDING)
        field_names = {field.name for field in agriculture.fields}
        self.assertIn("qualifying_examination", field_names)
        self.assertIn("selection_process", field_names)

    def test_page_with_two_courses(self) -> None:
        names = [course.course_name for course in self.undergraduate.courses]

        self.assertEqual(len(names), 2)
        self.assertTrue(any("Community Science" in name for name in names))

    def test_specialization_table_forward_fills_merged_cells(self) -> None:
        computer_science = next(
            course
            for course in self.engineering.courses
            if "Computer Science" in course.course_name
        )
        table = computer_science.tables[0]

        self.assertEqual(len(table.rows), 3)
        self.assertEqual(table.rows[0]["course_code"].text, "SPMEA")
        self.assertEqual(table.rows[1]["duration"].text, "4 Semesters")
        self.assertTrue(table.rows[1]["duration"].inherited)
        self.assertEqual(table.rows[2]["intake"].text, "20")
        self.assertTrue(table.rows[2]["intake"].inherited)

    def test_faculty_context_is_retained(self) -> None:
        self.assertTrue(
            all(
                course.faculty == "Faculty of Engineering & Technology"
                for course in self.engineering.courses
            )
        )


if __name__ == "__main__":
    unittest.main()

