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
        cls.narrative_mentions = CourseParser().parse(
            extractor.extract_pages([21, 34, 186])
        )
        cls.undergraduate_span = CourseParser().parse(
            extractor.extract_pages([54, 55, 56])
        )
        cls.section_boundary = CourseParser().parse(
            extractor.extract_pages([116, 117])
        )
        cls.noncontiguous = CourseParser().parse(
            extractor.extract_pages([54, 80])
        )
        cls.medical_postgraduate = CourseParser().parse(
            extractor.extract_pages([92, 93]),
            initial_faculty="Faculty of Medicine",
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

    def test_narrative_course_of_study_mentions_are_rejected(self) -> None:
        self.assertEqual(self.narrative_mentions.courses, [])

    def test_unlabelled_field_continuation_is_attached_to_previous_course(self) -> None:
        community_science = next(
            course
            for course in self.undergraduate_span.courses
            if "Community Science" in course.course_name
        )
        additional = next(
            field
            for field in community_science.fields
            if field.name == "additional_information"
        )

        self.assertIn("Only those candidates", additional.value)
        self.assertIn("eligible for Counseling and Admission", additional.value)
        self.assertNotIn("Information Admission Test", additional.value)

    def test_cross_page_course_adds_continued_and_new_fields(self) -> None:
        arts_courses = [
            course
            for course in self.undergraduate_span.courses
            if course.source.physical_page == 55
            and course.course_name == "B.A. (Hons.)"
        ]
        english_course = next(
            course
            for course in arts_courses
            if any(
                row.get("major_subject")
                and row["major_subject"].text == "English"
                for table in course.tables
                for row in table.rows
            )
        )
        fields = {field.name: field.value for field in english_course.fields}

        self.assertIn("Bridge Course-Senior Secondary", fields["qualifying_examination"])
        self.assertNotIn("Examination 50%", fields["qualifying_examination"])
        self.assertIn("age_limit", fields)
        self.assertIn("selection_process", fields)
        self.assertIn("test_paper_details", fields)
        self.assertIn("test_centres", fields)
        self.assertIn("additional_information", fields)
        self.assertIn("Faculties of Arts and Social Sciences", fields["additional_information"])
        self.assertNotIn("Faculties of Information Arts", fields["additional_information"])

    def test_large_next_section_heading_stops_continuation(self) -> None:
        bridge_course = next(
            course
            for course in self.section_boundary.courses
            if course.course_name.startswith("Bridge Course")
        )
        field_text = " ".join(field.value for field in bridge_course.fields)

        self.assertNotIn("Centre of Professional Courses", field_text)
        self.assertNotIn("Self Finance Mode", field_text)

    def test_plural_courses_of_study_headings_are_parsed(self) -> None:
        names = [course.course_name for course in self.medical_postgraduate.courses]

        self.assertEqual(
            names,
            [
                "Doctor of Medicine (M.D.)",
                "Master of Surgery (M.S.)",
                "Magister Chirurgiae (M.Ch.)",
                "Doctor of Medicine (D.M.)",
                "P.G. Diploma",
                "Post Doctoral Certificate Course (PDCC)",
                "Master of Public Health ( Under Self Financing Scheme )",
                "Master of Dental Surgery (M.D.S.)",
                "Master of Medical Laboratory Science ( Under Self Financing Scheme )",
            ],
        )

    def test_discipline_and_course_of_study_columns_are_kept_separate(self) -> None:
        courses = {course.course_name: course for course in self.medical_postgraduate.courses}
        md_rows = courses["Doctor of Medicine (M.D.)"].tables[0].rows
        pdcc = courses["Post Doctoral Certificate Course (PDCC)"]
        public_health = courses["Master of Public Health ( Under Self Financing Scheme )"]

        self.assertEqual(len(md_rows), 16)
        self.assertEqual(md_rows[0]["duration"].text, "3 Years")
        self.assertEqual(md_rows[0]["discipline"].text, "Anatomy")
        self.assertTrue(md_rows[-1]["duration"].inherited)
        self.assertEqual(pdcc.tables[0].rows[0]["specialization"].text, "Critical Care Medicine")
        self.assertIn("NATIONAL MEDICAL COMMISSION", pdcc.fields[-1].value)
        # The PDCC remarks must not leak into the following course card.
        self.assertNotIn("remarks", {field.name for field in public_health.fields})

    def test_nonconsecutive_pages_are_not_merged(self) -> None:
        community_science = next(
            course
            for course in self.noncontiguous.courses
            if "Community Science" in course.course_name
        )
        field_text = " ".join(field.value for field in community_science.fields)

        self.assertNotIn("GATE in Chemical Engineering", field_text)


if __name__ == "__main__":
    unittest.main()
