"""Inspect course-alias expansion and query routing."""

from __future__ import annotations

import argparse

from amu_admissions_rag.query_processing import QueryProcessor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Expand admissions course aliases")
    parser.add_argument("query", help="User admissions question")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print internal intent and alias details as JSON",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    analysis = QueryProcessor().analyze(args.query)
    if args.debug:
        print(analysis.model_dump_json(indent=2))
    else:
        print(analysis.expanded_query)


if __name__ == "__main__":
    main()
