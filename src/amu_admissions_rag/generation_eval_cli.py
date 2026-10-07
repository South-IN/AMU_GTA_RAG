"""Run a varied live retrieval-and-generation evaluation against Groq."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path

from amu_admissions_rag.config import AppPaths
from amu_admissions_rag.corpus import load_approved_corpora
from amu_admissions_rag.generation import GroqAnswerGenerator, load_env_file
from amu_admissions_rag.models import RetrievalHit
from amu_admissions_rag.retrieval import HybridRetriever, format_llm_context


@dataclass(frozen=True)
class EvaluationCase:
    query: str
    limit: int = 1
    discover_courses: bool = False


EVALUATION_CASES: tuple[EvaluationCase, ...] = (
    EvaluationCase("I have 12 credits in Mathematics. Can I do M.C.A.?"),
    EvaluationCase("How are candidates selected for M.B.A.?"),
    EvaluationCase("What specializations, duration and intake are offered in M.Tech CSE?"),
    EvaluationCase("What are the eligibility and selection requirements for M.B.B.S.?"),
    EvaluationCase("How long is B.A.LL.B. and what is its age limit?"),
    EvaluationCase("What qualification is required for M.Sc. Ag Microbiology?"),
    EvaluationCase(
        "I completed B.Sc. Computer Science. Which postgraduate courses in this guide may fit my background?",
        limit=3,
        discover_courses=True,
    ),
    EvaluationCase(
        "Tell me the available Diploma in Engineering branches, duration and intake."
    ),
)


def _markdown_case(
    number: int,
    case: EvaluationCase,
    expanded_query: str,
    context: str,
    answer: str,
    hits: list[RetrievalHit],
) -> str:
    mode = "course discovery" if case.discover_courses else "hybrid retrieval"
    sources = "\n".join(
        f"- `[SOURCE {source_number}]` {hit.chunk.title} — page "
        f"{hit.chunk.source.printed_page or hit.chunk.source.physical_page}"
        for source_number, hit in enumerate(hits, start=1)
    )
    return f"""## {number}. {case.query}

**Retrieval mode:** {mode}

**Expanded query:** {expanded_query}

### Retrieved context

```text
{context}
```

### LLM answer

{answer}

### Sources

{sources}
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run live answer-generation evaluation")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/PHASE9_LIVE_EVALUATION.md"),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    paths = AppPaths.from_package()
    load_env_file(paths.project_root / ".env")
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise SystemExit("GROQ_API_KEY is not configured")
    model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
    index, courses = load_approved_corpora(paths)
    retriever = HybridRetriever(index, courses)
    generator = GroqAnswerGenerator(api_key, model=model)
    sections: list[str] = []
    for number, case in enumerate(EVALUATION_CASES, start=1):
        if case.discover_courses:
            response = retriever.discover_courses(case.query, limit=case.limit)
            hits = [candidate.profile for candidate in response.candidates]
        else:
            response = retriever.search(case.query, limit=case.limit)
            hits = response.hits
        context = format_llm_context(hits)
        answer = generator.generate(case.query, context)
        sections.append(
            _markdown_case(
                number,
                case,
                response.query.expanded_query,
                context,
                answer,
                hits,
            )
        )
        print(f"Completed {number}/{len(EVALUATION_CASES)}")

    report = "\n".join(
        [
            "# Phase 9 Live Retrieval and Generation Evaluation",
            "",
            f"Model: `{model}`  ",
            f"Cases: {len(EVALUATION_CASES)}  ",
            "Corpus: 15-course human-approved validation checkpoint",
            "",
            "Each case records the exact query, expanded query, retrieved context and LLM answer.",
            "",
            *sections,
        ]
    )
    output = args.output if args.output.is_absolute() else paths.project_root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
