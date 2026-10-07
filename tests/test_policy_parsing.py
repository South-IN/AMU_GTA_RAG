import unittest

from amu_admissions_rag.config import AppPaths
from amu_admissions_rag.extraction import PdfExtractor
from amu_admissions_rag.models import AppendixType, ReviewStatus
from amu_admissions_rag.parsing import PolicyParser


class PolicyParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        paths = AppPaths.from_package()
        extractor = PdfExtractor(paths.source_pdf)
        pages = [
            19,
            31,
            45,
            51,
            53,
            128,
            129,
            130,
            136,
            148,
            149,
            150,
            172,
            173,
            187,
        ]
        cls.corpus = PolicyParser(max_chunk_words=180).parse(
            extractor.extract_pages(pages)
        )
        # Page 3 holds the CONTENTS; sections carry over between contiguous pages.
        cls.contents_corpus = PolicyParser().parse(
            extractor.extract_pages([3, *range(19, 26), 35, 45, 52, 53, 169, 187])
        )

    def test_policy_chunks_keep_headings_pages_and_pending_state(self) -> None:
        important = [
            record
            for record in self.corpus.sections
            if record.source.physical_page == 19
        ]

        self.assertTrue(important)
        self.assertEqual(important[0].heading, "IMPORTANT INFORMATION AND RULES")
        self.assertTrue(all(record.review.status is ReviewStatus.PENDING for record in important))
        self.assertTrue(all(record.source.bounding_box is not None for record in important))

    def test_sections_follow_the_contents_page(self) -> None:
        by_page: dict[int, set[str]] = {}
        for record in self.contents_corpus.sections:
            section = record.heading_path[0] if record.heading_path else record.heading
            by_page.setdefault(record.source.physical_page, set()).add(section)

        self.assertIn("Important Information and Rules", by_page[24])
        self.assertIn("Rules for admission for persons with benchmark disabilities", by_page[24])
        self.assertEqual(by_page[45], {"How to Obtain and Fill the Application Form"})
        self.assertIn("Refund of fee", by_page[52])
        # Pages outside the contents take their own heading, not a stale one.
        self.assertEqual(by_page[187], {"DISCLAIMER"})
        self.assertTrue(
            all("Special Categories" not in section for section in by_page[187] | by_page[45])
        )

    def test_unbolded_fragments_and_table_labels_are_not_headings(self) -> None:
        headings = {record.heading for record in self.contents_corpus.sections}

        for fragment in [
            "of the Major / Minor Subject defined as follows",
            "Controller’s Office website",
            "circumstances",
            "do hereby undertake the following",
            "Note",
            "TABLE IV",
        ]:
            self.assertNotIn(fragment, headings)
        self.assertIn("APPENDIX - VIII CONSENT FORM FOR PHYSICAL FITNESS TEST (PFT)", headings)
        self.assertGreaterEqual(
            min(len(record.text.split()) for record in self.contents_corpus.sections), 10
        )

    def test_policy_chunks_remove_repeated_headers_without_losing_rules(self) -> None:
        text = "\n".join(record.text for record in self.corpus.sections)

        self.assertNotIn("Aligarh Muslim University Guide to Admissions 2026-27", text)
        self.assertIn("Admissions to all courses of study", text)
        self.assertIn("Negative Marking", text)
        self.assertIn("University EPABX", text)
        self.assertIn("warranty, express or implied", text)

    def test_application_rows_forward_fill_visually_merged_values(self) -> None:
        linguistics = next(
            record
            for record in self.corpus.appendix_rows
            if record.appendix_type is AppendixType.APPLICATION_SUMMARY
            and record.course_code == "LNBAA"
        )

        self.assertEqual(linguistics.values["processing_charges"].text, "Rs. 750.00")
        self.assertEqual(linguistics.values["closing_without_late_fee"].text, "05-04-2026")
        self.assertTrue(linguistics.values["processing_charges"].inherited)
        self.assertEqual(linguistics.faculty, "Faculty of Arts")

    def test_test_schedule_retains_multi_paper_and_inherited_schedule(self) -> None:
        agriculture = next(
            record
            for record in self.corpus.appendix_rows
            if record.appendix_type is AppendixType.TEST_SCHEDULE
            and record.course_code == "AGBGA"
        )
        communicative_english = next(
            record
            for record in self.corpus.appendix_rows
            if record.appendix_type is AppendixType.TEST_SCHEDULE
            and record.course_code == "CNBAA"
        )

        self.assertIn("Paper- II: 2 hours", agriculture.values["duration"].text)
        self.assertIn("10:00 A.M.", agriculture.values["scheduled_start"].text)
        self.assertEqual(communicative_english.values["date_or_method"].text, "12-04-2026")
        self.assertTrue(communicative_english.values["date_or_method"].inherited)
        self.assertEqual(
            communicative_english.programme_group,
            "UNDERGRADUATE PROGAMMES",
        )

    def test_application_method_and_deferred_dates_are_not_misaligned(self) -> None:
        mbbs = next(
            record
            for record in self.corpus.appendix_rows
            if record.appendix_type is AppendixType.APPLICATION_SUMMARY
            and record.course_code == "MBBDA"
        )
        critical_care = next(
            record
            for record in self.corpus.appendix_rows
            if record.appendix_type is AppendixType.APPLICATION_SUMMARY
            and record.course_code == "CCCDA"
        )

        self.assertEqual(mbbs.values["application_form_details"].text, "Through NEET-UG")
        self.assertNotIn("processing_charges", mbbs.values)
        self.assertEqual(critical_care.values["processing_charges"].text, "Rs. 1150.00")
        self.assertEqual(
            critical_care.values["application_form_details"].text,
            "Will be notified separately",
        )
        self.assertEqual(
            critical_care.values["form_handling_office"].text,
            "Department of Anesthesiology",
        )

    def test_extraction_spacing_artifact_is_removed_from_course_name(self) -> None:
        python_certificate = next(
            record
            for record in self.corpus.appendix_rows
            if record.appendix_type is AppendixType.APPLICATION_SUMMARY
            and record.serial_number == "42"
            and record.source.physical_page == 148
        )

        self.assertEqual(
            python_certificate.course_name,
            "Certificate in Computer Programming (Python)",
        )

    def test_fee_rows_are_structured(self) -> None:
        agriculture = next(
            record
            for record in self.corpus.appendix_rows
            if record.appendix_type is AppendixType.FEE_SUMMARY
            and record.course_name == "B.Sc. (Hons.) Agriculture"
        )

        self.assertEqual(agriculture.values["fee_at_admission"].text, "58900")
        self.assertEqual(agriculture.faculty, "Faculty of Agricultural Sciences")
        self.assertEqual(agriculture.source.printed_page, "J.45")

    def test_record_ids_are_unique(self) -> None:
        record_ids = [record.record_id for record in self.corpus.sections]
        record_ids.extend(record.record_id for record in self.corpus.appendix_rows)

        self.assertEqual(len(record_ids), len(set(record_ids)))


if __name__ == "__main__":
    unittest.main()
