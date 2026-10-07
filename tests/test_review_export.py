import unittest

from amu_admissions_rag.models import (
    BoundingBox,
    CourseCorpus,
    CourseField,
    CourseRecord,
    CourseTable,
    CourseTableCell,
    DocumentRecord,
    ProgramLevel,
    SourceReference,
)
from amu_admissions_rag.review_export import build_human_review_payload


class HumanReviewExportTests(unittest.TestCase):
    def test_export_removes_technical_metadata_and_keeps_review_content(self) -> None:
        source = SourceReference(
            document_id="guide",
            physical_page=80,
            printed_page="B.11",
            section="Faculty of Engineering & Technology",
            bounding_box=BoundingBox(x0=1, top=2, x1=3, bottom=4),
        )
        corpus = CourseCorpus(
            document=DocumentRecord(
                document_id="guide",
                filename="guide.pdf",
                academic_year="2026-27",
                sha256="a" * 64,
                total_pages=187,
            ),
            courses=[
                CourseRecord(
                    record_id="guide:80:1:mtech-cse",
                    document_id="guide",
                    course_name="M.Tech CSE",
                    program_level=ProgramLevel.POSTGRADUATE,
                    faculty="Faculty of Engineering & Technology",
                    source=source,
                    fields=[
                        CourseField(
                            name="qualifying_examination",
                            label="Qualifying Examination",
                            value="B.Tech in a relevant branch",
                            source=source,
                        )
                    ],
                    tables=[
                        CourseTable(
                            name="course_details",
                            headers=["specialization", "intake"],
                            rows=[
                                {
                                    "specialization": CourseTableCell(
                                        text="Information Security"
                                    ),
                                    "intake": CourseTableCell(
                                        text="20", inherited=True
                                    ),
                                }
                            ],
                            source=source,
                        )
                    ],
                )
            ],
        )

        payload = build_human_review_payload(corpus)
        course = payload["courses"][0]

        self.assertEqual(payload["guide"]["academic_year"], "2026-27")
        self.assertEqual(course["source"]["printed_page"], "B.11")
        self.assertEqual(course["fields"][0]["value"], "B.Tech in a relevant branch")
        self.assertTrue(course["tables"][0]["rows"][0]["intake"]["inherited"])
        self.assertEqual(course["review"]["status"], "pending")

        forbidden = {"bounding_box", "document_id", "record_id", "sha256"}

        def collect_keys(value: object) -> set[str]:
            if isinstance(value, dict):
                return set(value) | {
                    key
                    for child in value.values()
                    for key in collect_keys(child)
                }
            if isinstance(value, list):
                return {
                    key
                    for child in value
                    for key in collect_keys(child)
                }
            return set()

        self.assertTrue(forbidden.isdisjoint(collect_keys(payload)))


if __name__ == "__main__":
    unittest.main()
