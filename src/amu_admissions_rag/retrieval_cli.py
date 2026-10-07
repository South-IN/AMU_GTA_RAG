"""Run an end-to-end query against the approved local retrieval corpus."""

from __future__ import annotations

import argparse
from pathlib import Path

from amu_admissions_rag.config import AppPaths
from amu_admissions_rag.models import CourseCorpus, IndexCorpus
from amu_admissions_rag.retrieval import HybridRetriever


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search the approved admissions corpus")
    parser.add_argument("query", help="Admissions question")
    parser.add_argument("--index", type=Path, help="Approved index-corpus JSON")
    parser.add_argument("--courses", type=Path, help="Reviewed course-corpus JSON")
    parser.add_argument("--limit", type=int, default=5, help="Number of hits to return")
    parser.add_argument("--json", action="store_true", help="Print the complete JSON result")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    paths = AppPaths.from_package()
    index_path = args.index or paths.processed_dir / "guide-2026-27.index-corpus.approved.json"
    course_path = args.courses or paths.review_dir / "guide-2026-27.course-corpus.reviewed.json"
    index_corpus = IndexCorpus.model_validate_json(index_path.read_text(encoding="utf-8"))
    course_corpus = CourseCorpus.model_validate_json(course_path.read_text(encoding="utf-8"))
    response = HybridRetriever(index_corpus, course_corpus).search(
        args.query,
        limit=args.limit,
    )
    if args.json:
        print(response.model_dump_json(indent=2))
        return

    print(f"Original: {response.query.original_query}")
    print(f"Retrieval query: {response.query.expanded_query}")
    print(f"Intents: {', '.join(intent.value for intent in response.query.intents)}")
    print(f"Vector provider: {response.embedding_provider}")
    for rank, hit in enumerate(response.hits, start=1):
        source = hit.chunk.source
        page = source.printed_page or str(source.physical_page)
        print(
            f"\n{rank}. {hit.chunk.title} "
            f"[{hit.chunk.chunk_type.value}; page {page}; score {hit.fused_score:.5f}]"
        )
        print(hit.chunk.text)
        parent = response.course_parents.get(hit.chunk.parent_record_id)
        if parent is not None:
            print(
                "Hydrated parent: "
                f"{parent.course_name} | {len(parent.fields)} fields | "
                f"{len(parent.tables)} tables"
            )


if __name__ == "__main__":
    main()
