"""Groq Chat Completions client for grounded admissions answers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"

SYSTEM_PROMPT = """You are an assistant for the AMU Guide to Admissions 2026-27.
Answer only from the supplied retrieved sources.
Every factual statement must cite one or more sources using exactly [SOURCE N].
Never invent a course, requirement, date, intake, fee, or page number.
For eligibility questions, compare only explicitly stated applicant facts with the source requirements. If required information is missing, say what is missing instead of declaring the applicant eligible.
If the sources do not support an answer, say that the provided guide evidence is insufficient.
Keep the answer concise and do not mention retrieval scores or internal metadata."""


def load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE entries without overriding process variables."""

    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip())


class GroqAnswerGenerator:
    def __init__(
        self,
        api_key: str,
        *,
        model: str = DEFAULT_GROQ_MODEL,
        timeout_seconds: int = 60,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Groq API key cannot be empty")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate(self, query: str, context: str) -> str:
        if not context.strip():
            return "The provided guide evidence is insufficient to answer this question."
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Question:\n{query}\n\nRetrieved sources:\n{context}",
                },
            ],
            "reasoning_effort": "low",
            "reasoning_format": "hidden",
            "temperature": 0.2,
            "max_completion_tokens": 800,
        }
        request = Request(
            GROQ_CHAT_COMPLETIONS_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "AMU-Admissions-RAG/0.1",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Groq API returned HTTP {error.code}: {detail}") from error
        except URLError as error:
            raise RuntimeError(f"Could not reach the Groq API: {error.reason}") from error
        try:
            answer = body["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, AttributeError) as error:
            raise RuntimeError("Groq API returned an unexpected response") from error
        if not answer:
            raise RuntimeError("Groq API returned an empty answer")
        return answer
