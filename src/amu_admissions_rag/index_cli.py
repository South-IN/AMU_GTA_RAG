"""Build approval-gated retrieval chunks from reviewed corpora."""

from __future__ import annotations

import argparse
from pathlib import Path

from amu_admissions_rag.config import AppPaths
from amu_admissions_rag.indexing import RetrievalChunkBuilder
from amu_admissions_rag.models import CourseCorpus, PolicyCorpus


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build self-contained retrieval chunks from reviewed records"
    )
    parser.add_argument("--courses", type=Path, help="Reviewed course-corpus JSON")
    parser.add_argument("--policies", type=Path, help="Reviewed policy-corpus JSON")
    parser.add_argument("--output", type=Path, help="Index-corpus JSON output")
    parser.add_argument(
        "--include-pending",
        action="store_true",
        help="Create a non-indexable preview containing pending records",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    paths = AppPaths.from_package()
    course_path = (
        args.courses
        or paths.review_dir / "guide-2026-27.course-corpus.pending.json"
    )
    policy_path = (
        args.policies
        or paths.review_dir / "guide-2026-27.policy-corpus.pending.json"
    )
    default_name = (
        "guide-2026-27.index-corpus.preview.json"
        if args.include_pending
        else "guide-2026-27.index-corpus.approved.json"
    )
    output = args.output or paths.processed_dir / default_name

    course_corpus = CourseCorpus.model_validate_json(
        course_path.read_text(encoding="utf-8")
    )
    policy_corpus = PolicyCorpus.model_validate_json(
        policy_path.read_text(encoding="utf-8")
    )
    corpus = RetrievalChunkBuilder().build(
        course_corpus,
        policy_corpus,
        include_pending=args.include_pending,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(corpus.model_dump_json(indent=2), encoding="utf-8")

    mode = "preview" if args.include_pending else "approved"
    print(f"Built {len(corpus.chunks)} {mode} retrieval chunk(s) at {output}")
    if not args.include_pending and not corpus.chunks:
        print("No approved records were found; pending records were not indexed.")


if __name__ == "__main__":
    main()
