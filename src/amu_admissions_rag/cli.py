"""Command-line entry points for corpus extraction."""

from __future__ import annotations

import argparse
from pathlib import Path

from amu_admissions_rag.config import AppPaths
from amu_admissions_rag.extraction import PdfExtractor, parse_page_spec


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract positioned text and tables from the guide")
    parser.add_argument("--pdf", type=Path, help="PDF path; defaults to the configured source guide")
    parser.add_argument("--pages", default="1", help="Physical pages, for example 1,54-56,128")
    parser.add_argument("--output", type=Path, help="Output JSON path")
    parser.add_argument("--no-tables", action="store_true", help="Skip table detection")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    paths = AppPaths.from_package()
    pdf_path = args.pdf or paths.source_pdf
    extractor = PdfExtractor(pdf_path)
    document = extractor.document_record()
    pages = parse_page_spec(args.pages, document.total_pages)
    result = extractor.extract_pages(pages, include_tables=not args.no_tables)

    output = args.output or paths.processed_dir / "extraction.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    print(f"Extracted {len(result.pages)} page(s) to {output}")


if __name__ == "__main__":
    main()

