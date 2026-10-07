"""Retrieve approved chunks and generate a cited answer with Groq."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from amu_admissions_rag.config import AppPaths
from amu_admissions_rag.generation import GroqAnswerGenerator, load_env_file
from amu_admissions_rag.models import (
    AnswerCitation,
    CourseCorpus,
    GeneratedAnswer,
    IndexCorpus,
    RetrievalHit,
)
from amu_admissions_rag.retrieval import HybridRetriever, format_llm_context


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a grounded admissions answer")
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--discover-courses", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    paths = AppPaths.from_package()
    load_env_file(paths.project_root / ".env")
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise SystemExit("GROQ_API_KEY is not configured")
    model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
    index = IndexCorpus.model_validate_json(
        (paths.processed_dir / "guide-2026-27.index-corpus.approved.json").read_text(
            encoding="utf-8"
        )
    )
    courses = CourseCorpus.model_validate_json(
        (paths.review_dir / "guide-2026-27.course-corpus.reviewed.json").read_text(
            encoding="utf-8"
        )
    )
    retriever = HybridRetriever(index, courses)
    hits: list[RetrievalHit]
    if args.discover_courses:
        discovery = retriever.discover_courses(args.query, limit=args.limit)
        hits = [candidate.profile for candidate in discovery.candidates]
    else:
        hits = retriever.search(args.query, limit=args.limit).hits
    context = format_llm_context(hits)
    answer = GroqAnswerGenerator(api_key, model=model).generate(args.query, context)
    result = GeneratedAnswer(
        query=args.query,
        answer=answer,
        citations=[
            AnswerCitation(
                source_number=number,
                chunk_id=hit.chunk.chunk_id,
                title=hit.chunk.title,
                printed_page=hit.chunk.source.printed_page,
                physical_page=hit.chunk.source.physical_page,
            )
            for number, hit in enumerate(hits, start=1)
        ],
        model=model,
        retrieved_chunk_ids=[hit.chunk.chunk_id for hit in hits],
    )
    if args.json:
        print(result.model_dump_json(indent=2))
        return
    print(result.answer)
    print("\nRetrieved sources:")
    for citation in result.citations:
        page = citation.printed_page or f"physical {citation.physical_page}"
        print(f"[{citation.source_number}] {citation.title} — page {page}")


if __name__ == "__main__":
    main()
