"""Format retrieved information chunks for the answer-generating LLM."""

from __future__ import annotations

from amu_admissions_rag.models import RetrievalHit


def format_llm_context(hits: list[RetrievalHit]) -> str:
    """Return content and citations only; omit scores and internal metadata."""

    blocks = []
    for number, hit in enumerate(hits, start=1):
        source = hit.chunk.source
        page = source.printed_page or f"physical page {source.physical_page}"
        blocks.append(
            "\n".join(
                [
                    f"[SOURCE {number}]",
                    f"Title: {hit.chunk.title}",
                    f"Citation: AMU Guide to Admissions 2026-27, page {page}",
                    "Content:",
                    hit.chunk.text,
                ]
            )
        )
    return "\n\n".join(blocks)
