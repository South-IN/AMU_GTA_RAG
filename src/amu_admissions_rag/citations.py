"""Shared parsing for model-generated source citation markers."""

from __future__ import annotations

import re


# Groq models may emit either Markdown-style brackets or Unicode citation brackets.
SOURCE_PATTERN = re.compile(
    r"(?:\[\s*SOURCE\s+(\d+)\s*\]|【\s*SOURCE\s+(\d+)\s*】)",
    re.IGNORECASE,
)


def source_number(match: re.Match[str]) -> int:
    """Return the source number from either supported marker style."""

    return int(match.group(1) or match.group(2))
