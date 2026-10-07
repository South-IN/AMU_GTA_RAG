from datetime import datetime, timezone
import unittest

from pydantic import ValidationError

from amu_admissions_rag.models import (
    CourseCorpus,
    CourseRecord,
    DocumentRecord,
    ProgramLevel,
    ReviewBatch,
    ReviewDecision,
    ReviewStatus,
    SourceReference,
)
from amu_admissions_rag.reviews import apply_course_review_batch


class ReviewBatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = DocumentRecord(
            document_id="guide",
            filename="guide.pdf",
            academic_year="2026-27",
            sha256="a" * 64,
            total_pages=187,
        )
        source = SourceReference(document_id="guide", physical_page=94)
        self.course = CourseRecord(
            record_id="guide:mca",
            document_id="guide",
            course_name="Master of Computer Science and Applications (MCA)",
            program_level=ProgramLevel.POSTGRADUATE,
            faculty="Faculty of Science",
            source=source,
        )

    def test_review_batch_records_approval_audit_fields(self) -> None:
        reviewed_at = datetime(2026, 10, 7, tzinfo=timezone.utc)
        batch = ReviewBatch(
            reviewer="project-owner",
            reviewed_at=reviewed_at,
            decisions=[
                ReviewDecision(
                    record_id=self.course.record_id,
                    status=ReviewStatus.APPROVED,
                    notes="Checked against the PDF.",
                )
            ],
        )

        result = apply_course_review_batch(
            CourseCorpus(document=self.document, courses=[self.course]),
            batch,
        )

        review = result.courses[0].review
        self.assertEqual(review.status, ReviewStatus.APPROVED)
        self.assertEqual(review.reviewer, "project-owner")
        self.assertEqual(review.reviewed_at, reviewed_at)
        self.assertEqual(review.notes, "Checked against the PDF.")

    def test_review_batch_rejects_unknown_record(self) -> None:
        batch = ReviewBatch(
            reviewer="project-owner",
            reviewed_at=datetime(2026, 10, 7, tzinfo=timezone.utc),
            decisions=[
                ReviewDecision(
                    record_id="unknown",
                    status=ReviewStatus.APPROVED,
                )
            ],
        )

        with self.assertRaisesRegex(ValueError, "unknown records"):
            apply_course_review_batch(
                CourseCorpus(document=self.document, courses=[self.course]),
                batch,
            )

    def test_pending_and_duplicate_decisions_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ReviewDecision(
                record_id=self.course.record_id,
                status=ReviewStatus.PENDING,
            )

        decision = ReviewDecision(
            record_id=self.course.record_id,
            status=ReviewStatus.APPROVED,
        )
        with self.assertRaises(ValidationError):
            ReviewBatch(
                reviewer="project-owner",
                reviewed_at=datetime(2026, 10, 7, tzinfo=timezone.utc),
                decisions=[decision, decision],
            )


if __name__ == "__main__":
    unittest.main()
