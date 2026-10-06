from datetime import datetime, timezone
import unittest

from pydantic import ValidationError

from amu_admissions_rag.models import (
    BoundingBox,
    CourseRecord,
    ProgramLevel,
    ReviewMetadata,
    ReviewStatus,
    SourceReference,
)


class ModelTests(unittest.TestCase):
    def test_pending_review_requires_no_reviewer(self) -> None:
        review = ReviewMetadata()

        self.assertEqual(review.status, ReviewStatus.PENDING)
        self.assertIsNone(review.reviewer)

    def test_approved_review_requires_audit_fields(self) -> None:
        with self.assertRaises(ValidationError):
            ReviewMetadata(status=ReviewStatus.APPROVED)

        review = ReviewMetadata(
            status=ReviewStatus.APPROVED,
            reviewer="reviewer@example.com",
            reviewed_at=datetime.now(timezone.utc),
        )
        self.assertEqual(review.status, ReviewStatus.APPROVED)

    def test_bounding_box_rejects_reversed_coordinates(self) -> None:
        with self.assertRaises(ValidationError):
            BoundingBox(x0=20, top=10, x1=5, bottom=30)

    def test_course_record_retains_source_and_review_state(self) -> None:
        source = SourceReference(
            document_id="amu-2026-27",
            physical_page=94,
            printed_page="B.25",
            section="Faculty of Science",
        )
        course = CourseRecord(
            record_id="amu-2026-27-mca",
            document_id="amu-2026-27",
            course_name="Master of Computer Science and Applications (MCA)",
            course_code="MCA",
            program_level=ProgramLevel.POSTGRADUATE,
            faculty="Faculty of Science",
            source=source,
        )

        self.assertEqual(course.source.printed_page, "B.25")
        self.assertEqual(course.review.status, ReviewStatus.PENDING)


if __name__ == "__main__":
    unittest.main()

