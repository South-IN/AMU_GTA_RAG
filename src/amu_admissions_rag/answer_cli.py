"""Retrieve approved chunks and generate a cited answer with Groq."""

from __future__ import annotations

import argparse

from amu_admissions_rag.assistant import AdmissionsAssistant
from amu_admissions_rag.models import (
    GeneratedAnswer,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a grounded admissions answer")
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--discover-courses", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        assistant = AdmissionsAssistant.from_project()
    except ValueError as error:
        raise SystemExit(str(error)) from error
    reply = assistant.ask(
        args.query,
        limit=args.limit,
        discover_courses=args.discover_courses,
    )
    result = GeneratedAnswer(
        query=args.query,
        answer=reply.answer,
        citations=reply.citations,
        model=reply.model,
        retrieved_chunk_ids=[hit.chunk.chunk_id for hit in reply.hits],
    )
    if args.json:
        print(result.model_dump_json(indent=2))
        return
    print(reply.answer)
    print("\nRetrieved sources:")
    for citation in result.citations:
        page = citation.printed_page or f"physical {citation.physical_page}"
        print(f"[{citation.source_number}] {citation.title} — page {page}")


if __name__ == "__main__":
    main()
