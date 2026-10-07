"""Evaluate top-k retrieval against a compact, human-readable query set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from amu_admissions_rag.config import AppPaths
from amu_admissions_rag.models import CourseCorpus, IndexCorpus
from amu_admissions_rag.retrieval import HybridRetriever


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate approved-corpus retrieval")
    parser.add_argument("--queries", type=Path, default=Path("evaluation/retrieval_queries.json"))
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    paths = AppPaths.from_package()
    index_corpus = IndexCorpus.model_validate_json(
        (paths.processed_dir / "guide-2026-27.index-corpus.approved.json").read_text(
            encoding="utf-8"
        )
    )
    course_corpus = CourseCorpus.model_validate_json(
        (paths.review_dir / "guide-2026-27.course-corpus.reviewed.json").read_text(
            encoding="utf-8"
        )
    )
    cases = json.loads(args.queries.read_text(encoding="utf-8"))
    retriever = HybridRetriever(index_corpus, course_corpus)
    results: list[dict[str, object]] = []
    passed = 0
    for case in cases:
        response = retriever.search(case["query"], limit=args.limit)
        expected_parent = case["expected_parent_record_id"]
        expected_field = case.get("expected_field")
        parent_match = any(
            hit.chunk.parent_record_id == expected_parent for hit in response.hits
        )
        field_match = expected_field is None or any(
            hit.chunk.parent_record_id == expected_parent
            and hit.chunk.field_name == expected_field
            for hit in response.hits
        )
        success = parent_match and field_match
        passed += int(success)
        result = {
            "query": case["query"],
            "expanded_query": response.query.expanded_query,
            "intents": [intent.value for intent in response.query.intents],
            "expected_parent_record_id": expected_parent,
            "expected_field": expected_field,
            "success": success,
            "hits": [
                {
                    "rank": rank,
                    "title": hit.chunk.title,
                    "chunk_type": hit.chunk.chunk_type.value,
                    "field_name": hit.chunk.field_name,
                    "parent_record_id": hit.chunk.parent_record_id,
                    "printed_page": hit.chunk.source.printed_page,
                    "score": round(hit.fused_score, 6),
                }
                for rank, hit in enumerate(response.hits, start=1)
            ],
        }
        results.append(result)
        status = "PASS" if success else "FAIL"
        top = response.hits[0].chunk.title if response.hits else "no result"
        print(f"{status}: {case['query']} -> {top}")

    report = {
        "embedding_provider": retriever.embedding_provider.name,
        "top_k": args.limit,
        "passed": passed,
        "total": len(cases),
        "accuracy": passed / len(cases) if cases else 0.0,
        "results": results,
    }
    print(f"\nTop-{args.limit}: {passed}/{len(cases)} ({report['accuracy']:.1%})")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
