from datetime import datetime, timezone
import unittest

from pydantic import ValidationError

from amu_admissions_rag.models import (
    CourseCorpus,
    CourseRecord,
    DocumentRecord,
    PolicyCorpus,
    ProgramLevel,
    ReviewBatch,
    ReviewDecision,
    ReviewStatus,
    SectionRecord,
    SourceReference,
)
from amu_admissions_rag.reviews import apply_course_review_batch, apply_review_batches


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

    def test_batches_are_routed_by_record_and_later_batches_win(self) -> None:
        section = SectionRecord(
            record_id="guide:refunds",
            document_id="guide",
            heading="Refunds",
            text="Refund rules.",
            source=SourceReference(document_id="guide", physical_page=52),
        )
        first = ReviewBatch(
            reviewer="first-reviewer",
            reviewed_at=datetime(2026, 10, 7, tzinfo=timezone.utc),
            decisions=[
                ReviewDecision(record_id=self.course.record_id, status=ReviewStatus.REJECTED),
                ReviewDecision(record_id=section.record_id, status=ReviewStatus.APPROVED),
            ],
        )
        second = ReviewBatch(
            reviewer="second-reviewer",
            reviewed_at=datetime(2026, 10, 8, tzinfo=timezone.utc),
            decisions=[
                ReviewDecision(record_id=self.course.record_id, status=ReviewStatus.APPROVED),
            ],
        )

        courses, policies = apply_review_batches(
            CourseCorpus(document=self.document, courses=[self.course]),
            PolicyCorpus(document=self.document, sections=[section], appendix_rows=[]),
            [first, second],
        )

        self.assertEqual(courses.courses[0].review.status, ReviewStatus.APPROVED)
        self.assertEqual(courses.courses[0].review.reviewer, "second-reviewer")
        self.assertEqual(policies.sections[0].review.status, ReviewStatus.APPROVED)
        self.assertEqual(policies.sections[0].review.reviewer, "first-reviewer")

    def test_routed_batches_reject_unknown_records(self) -> None:
        batch = ReviewBatch(
            reviewer="project-owner",
            reviewed_at=datetime(2026, 10, 7, tzinfo=timezone.utc),
            decisions=[ReviewDecision(record_id="unknown", status=ReviewStatus.APPROVED)],
        )
        with self.assertRaisesRegex(ValueError, "unknown records"):
            apply_review_batches(
                CourseCorpus(document=self.document, courses=[self.course]),
                PolicyCorpus(document=self.document, sections=[], appendix_rows=[]),
                [batch],
            )


if __name__ == "__main__":
    unittest.main()
