"""Apply an auditable human-review batch to a corpus JSON file."""

from __future__ import annotations

import argparse
from pathlib import Path

from amu_admissions_rag.models import CourseCorpus, PolicyCorpus, ReviewBatch
from amu_admissions_rag.reviews import (
    apply_course_review_batch,
    apply_policy_review_batch,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply human-review decisions")
    parser.add_argument("--kind", choices=("courses", "policies"), required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    batch = ReviewBatch.model_validate_json(
        args.decisions.read_text(encoding="utf-8")
    )
    source = args.input.read_text(encoding="utf-8")
    if args.kind == "courses":
        corpus = apply_course_review_batch(
            CourseCorpus.model_validate_json(source),
            batch,
        )
    else:
        corpus = apply_policy_review_batch(
            PolicyCorpus.model_validate_json(source),
            batch,
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(corpus.model_dump_json(indent=2), encoding="utf-8")
    print(f"Applied {len(batch.decisions)} review decision(s) to {args.output}")


if __name__ == "__main__":
    main()
