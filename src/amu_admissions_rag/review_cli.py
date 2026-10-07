"""Export a metadata-light course corpus for human review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from amu_admissions_rag.config import AppPaths
from amu_admissions_rag.models import CourseCorpus
from amu_admissions_rag.review_export import build_human_review_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Remove technical extraction metadata from a course corpus"
    )
    parser.add_argument("--input", type=Path, help="Pending course-corpus JSON path")
    parser.add_argument("--output", type=Path, help="Human-review JSON path")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    paths = AppPaths.from_package()
    source = args.input or paths.review_dir / "course_records.pending.json"
    output = args.output or paths.review_dir / "course_records.human-review.json"

    corpus = CourseCorpus.model_validate_json(source.read_text(encoding="utf-8"))
    payload = build_human_review_payload(corpus)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Exported {len(corpus.courses)} human-review record(s) to {output}")


if __name__ == "__main__":
    main()
