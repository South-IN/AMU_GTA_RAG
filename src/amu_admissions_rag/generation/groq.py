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
The retrieved sources can contain course-specific information, appendix records, and applicable guide-wide admissions policies. Apply relevant guide-wide policies together with the course-specific requirements, but do not apply a policy when the source does not support its relevance. If a policy qualifies or limits a course-specific statement, explain that relationship and cite both sources.
Every factual statement must cite one or more sources using exactly [SOURCE N].
Never invent a course, requirement, date, intake, fee, or page number.
For eligibility questions, compare only explicitly stated applicant facts with the source requirements. If required information is missing, say what is missing instead of declaring the applicant eligible.
Treat course-discovery results as potential matches, not eligibility decisions. Never say that an applicant qualifies or satisfies the conditions unless every cited requirement is explicitly established by the question. A degree title alone does not establish marks, subject credits, age, or other prerequisites.
If the sources do not support an answer, say that the provided guide evidence is insufficient.
Keep the answer concise and do not mention retrieval scores or internal metadata."""

CITATION_REPAIR_PROMPT = """Repair citations in an admissions answer.
Use only the supplied retrieved sources. Preserve supported answer content, remove unsupported claims, and attach [SOURCE N] to every factual statement. Use only source numbers present in the retrieved sources. Return only the repaired answer."""

ELIGIBILITY_REPAIR_PROMPT = """Rewrite a course-discovery answer to avoid unsupported eligibility claims.
The applicant facts are exactly those stated in the question; never infer marks, subject credits, age, course duration, or prerequisite subjects. Describe courses only as potential matches. For each candidate, distinguish stated facts from requirements that remain unverified. Do not say the applicant qualifies, is eligible, can apply, satisfies conditions, or meets all criteria unless every cited requirement is explicitly stated in the question. Use only the retrieved sources and retain valid [SOURCE N] citations. Return only the corrected answer."""


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
        return self._complete(
            SYSTEM_PROMPT,
            f"Question:\n{query}\n\nRetrieved sources:\n{context}",
        )

    def repair_citations(self, query: str, context: str, answer: str) -> str:
        """Make one constrained pass to repair missing or invalid source markers."""

        if not context.strip():
            return answer
        return self._complete(
            CITATION_REPAIR_PROMPT,
            "\n\n".join(
                [
                    f"Question:\n{query}",
                    f"Retrieved sources:\n{context}",
                    f"Answer to repair:\n{answer}",
                ]
            ),
        )

    def repair_eligibility_claims(self, query: str, context: str, answer: str) -> str:
        """Rewrite an overconfident discovery answer using only stated applicant facts."""

        if not context.strip():
            return answer
        return self._complete(
            ELIGIBILITY_REPAIR_PROMPT,
            "\n\n".join(
                [
                    f"Question:\n{query}",
                    f"Retrieved sources:\n{context}",
                    f"Answer to correct:\n{answer}",
                ]
            ),
        )

    def _complete(self, system_prompt: str, user_content: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "reasoning_effort": "low",
            "reasoning_format": "hidden",
            "temperature": 0.0,
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
