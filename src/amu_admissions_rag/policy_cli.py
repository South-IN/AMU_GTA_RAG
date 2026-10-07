"""Build pending policy chunks and structured appendix rows."""

from __future__ import annotations

import argparse
from pathlib import Path

from amu_admissions_rag.config import AppPaths
from amu_admissions_rag.models import ExtractedDocument
from amu_admissions_rag.parsing import PolicyParser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse required non-course pages into pending policy records"
    )
    parser.add_argument("--input", type=Path, help="Full extraction JSON path")
    parser.add_argument("--output", type=Path, help="Pending policy-corpus JSON path")
    parser.add_argument(
        "--max-chunk-words",
        type=int,
        default=300,
        help="Maximum words per policy chunk (minimum: 50)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    paths = AppPaths.from_package()
    source = args.input or paths.processed_dir / "guide-2026-27.full-extraction.json"
    output = args.output or paths.review_dir / "guide-2026-27.policy-corpus.pending.json"

    extracted = ExtractedDocument.model_validate_json(source.read_text(encoding="utf-8"))
    corpus = PolicyParser(max_chunk_words=args.max_chunk_words).parse(extracted)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(corpus.model_dump_json(indent=2), encoding="utf-8")
    print(
        f"Parsed {len(corpus.sections)} policy chunk(s) and "
        f"{len(corpus.appendix_rows)} appendix row(s) to {output}"
    )


if __name__ == "__main__":
    main()
