"""Apply auditable human-review decisions to extracted corpora."""

from __future__ import annotations

from amu_admissions_rag.models import (
    CourseCorpus,
    PolicyCorpus,
    ReviewBatch,
    ReviewDecision,
    ReviewMetadata,
)


def apply_course_review_batch(
    corpus: CourseCorpus,
    batch: ReviewBatch,
) -> CourseCorpus:
    decisions = {decision.record_id: decision for decision in batch.decisions}
    known_ids = {record.record_id for record in corpus.courses}
    _require_known_ids(decisions, known_ids)
    courses = [
        record.model_copy(
            update={"review": _review_metadata(batch, decisions[record.record_id])}
        )
        if record.record_id in decisions
        else record
        for record in corpus.courses
    ]
    return corpus.model_copy(update={"courses": courses})


def apply_policy_review_batch(
    corpus: PolicyCorpus,
    batch: ReviewBatch,
) -> PolicyCorpus:
    decisions = {decision.record_id: decision for decision in batch.decisions}
    known_ids = {
        record.record_id
        for record in [*corpus.sections, *corpus.appendix_rows]
    }
    _require_known_ids(decisions, known_ids)
    sections = [
        record.model_copy(
            update={"review": _review_metadata(batch, decisions[record.record_id])}
        )
        if record.record_id in decisions
        else record
        for record in corpus.sections
    ]
    appendix_rows = [
        record.model_copy(
            update={"review": _review_metadata(batch, decisions[record.record_id])}
        )
        if record.record_id in decisions
        else record
        for record in corpus.appendix_rows
    ]
    return corpus.model_copy(
        update={"sections": sections, "appendix_rows": appendix_rows}
    )


def _review_metadata(
    batch: ReviewBatch,
    decision: ReviewDecision,
) -> ReviewMetadata:
    return ReviewMetadata(
        status=decision.status,
        reviewer=batch.reviewer,
        reviewed_at=batch.reviewed_at,
        notes=decision.notes,
    )


def _require_known_ids(
    decisions: dict[str, ReviewDecision],
    known_ids: set[str],
) -> None:
    missing = sorted(set(decisions) - known_ids)
    if missing:
        raise ValueError(f"review decisions reference unknown records: {missing}")
