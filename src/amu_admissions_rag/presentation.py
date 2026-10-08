"""Presentation helpers shared by the Streamlit UI and tests."""

from __future__ import annotations

import re

from amu_admissions_rag.citations import SOURCE_PATTERN, source_number


def link_answer_citations(answer: str, valid_source_numbers: list[int]) -> str:
    """Convert valid model source markers to local Markdown anchor links."""

    valid = set(valid_source_numbers)

    def replace(match: re.Match[str]) -> str:
        number = source_number(match)
        if number not in valid:
            return match.group(0)
        return f"[{number}](#source-{number})"

    return SOURCE_PATTERN.sub(replace, answer)


def context_preview(text: str, limit: int = 360) -> str:
    """Create a compact source-card preview without cutting through a word."""

    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    shortened = compact[:limit].rsplit(" ", 1)[0]
    return f"{shortened}…"
