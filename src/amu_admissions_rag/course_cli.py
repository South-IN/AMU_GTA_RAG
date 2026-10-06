"""Create pending course records for human validation."""

from __future__ import annotations

import argparse
from pathlib import Path

from amu_admissions_rag.config import AppPaths
from amu_admissions_rag.extraction import PdfExtractor, parse_page_spec
from amu_admissions_rag.parsing import CourseParser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse course pages into pending records")
    parser.add_argument("--pdf", type=Path, help="PDF path; defaults to the configured source guide")
    parser.add_argument("--pages", default="54-127", help="Physical course pages")
    parser.add_argument("--output", type=Path, help="Output JSON path")
    parser.add_argument("--initial-faculty", help="Faculty context before the first selected page")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    paths = AppPaths.from_package()
    extractor = PdfExtractor(args.pdf or paths.source_pdf)
    document = extractor.document_record()
    pages = parse_page_spec(args.pages, document.total_pages)
    extracted = extractor.extract_pages(pages)
    corpus = CourseParser().parse(extracted, initial_faculty=args.initial_faculty)

    output = args.output or paths.review_dir / "course_records.pending.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(corpus.model_dump_json(indent=2), encoding="utf-8")
    print(f"Parsed {len(corpus.courses)} pending course record(s) to {output}")


if __name__ == "__main__":
    main()

