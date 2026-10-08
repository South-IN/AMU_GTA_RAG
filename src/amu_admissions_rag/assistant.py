"""Reusable orchestration service for admissions retrieval and generation."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from amu_admissions_rag.citations import SOURCE_PATTERN, source_number
from amu_admissions_rag.config import AppPaths
from amu_admissions_rag.corpus import load_approved_corpora
from amu_admissions_rag.generation import GroqAnswerGenerator, load_env_file
from amu_admissions_rag.models import (
    AnswerCitation,
    ChunkType,
    QueryAnalysis,
    RetrievalHit,
)
from amu_admissions_rag.retrieval import HybridRetriever, format_llm_context


DISCOVERY_PATTERN = re.compile(
    r"\b(?:which|what)\s+(?:postgraduate\s+|undergraduate\s+)?courses?\b"
    r"|\bcourses?\s+(?:can|could|should|may)\s+i\b"
    r"|\b(?:recommend|suggest)\b.{0,30}\bcourses?\b",
    re.IGNORECASE,
)
OVERCONFIDENT_ELIGIBILITY_PATTERN = re.compile(
    r"\b(?:qualif(?:y|ies|ied)|eligible|satisf(?:y|ies|ied)|meets?\s+all|can\s+apply)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AssistantReply:
    query: QueryAnalysis
    answer: str
    hits: list[RetrievalHit]
    citations: list[AnswerCitation]
    context: str
    model: str
    retrieval_mode: str
    cited_source_numbers: list[int]
    citation_repair_attempted: bool
    eligibility_repair_attempted: bool
    citation_warning: str | None = None


def cited_source_numbers(answer: str, source_count: int) -> tuple[list[int], list[int]]:
    """Return unique valid and invalid source numbers used by an answer."""

    referenced = list(
        dict.fromkeys(source_number(match) for match in SOURCE_PATTERN.finditer(answer))
    )
    valid = [number for number in referenced if 1 <= number <= source_count]
    invalid = [number for number in referenced if number not in valid]
    return valid, invalid


def should_discover_courses(query: str) -> bool:
    """Detect questions asking for course suggestions rather than one course."""

    return bool(DISCOVERY_PATTERN.search(query))


class AdmissionsAssistant:
    """Coordinate query processing, hybrid retrieval and grounded generation."""

    def __init__(self, retriever: HybridRetriever, generator: GroqAnswerGenerator) -> None:
        self.retriever = retriever
        self.generator = generator

    @property
    def model(self) -> str:
        return self.generator.model

    @classmethod
    def from_project(cls, paths: AppPaths | None = None) -> "AdmissionsAssistant":
        paths = paths or AppPaths.from_package()
        load_env_file(paths.project_root / ".env")
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            raise ValueError("GROQ_API_KEY is not configured")
        model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
        index, courses = load_approved_corpora(paths)
        return cls(HybridRetriever(index, courses), GroqAnswerGenerator(api_key, model=model))

    def ask(
        self,
        query: str,
        *,
        limit: int | None = None,
        discover_courses: bool | None = None,
        policy_limit: int = 2,
    ) -> AssistantReply:
        if policy_limit < 0:
            raise ValueError("policy_limit cannot be negative")
        discovery = should_discover_courses(query) if discover_courses is None else discover_courses
        effective_limit = limit or (3 if discovery else 1)
        if discovery:
            response = self.retriever.discover_courses(query, limit=effective_limit)
            hits = [candidate.profile for candidate in response.candidates]
            mode = "course_discovery"
        else:
            response = self.retriever.search(query, limit=effective_limit)
            hits = response.hits
            mode = "hybrid_retrieval"

        if policy_limit:
            policy_response = self.retriever.search(
                query,
                limit=policy_limit,
                chunk_types={ChunkType.POLICY_SECTION},
            )
            hits = self._deduplicate_hits([*hits, *policy_response.hits])

        context = format_llm_context(hits)
        answer = self.generator.generate(query, context)
        eligibility_repair_attempted = False
        if discovery and OVERCONFIDENT_ELIGIBILITY_PATTERN.search(answer):
            eligibility_repair_attempted = True
            answer = self.generator.repair_eligibility_claims(query, context, answer)
        valid, invalid = cited_source_numbers(answer, len(hits))
        repair_attempted = False
        needs_citations = bool(hits) and "evidence is insufficient" not in answer.casefold()
        if invalid or (needs_citations and not valid):
            repair_attempted = True
            answer = self.generator.repair_citations(query, context, answer)
            valid, invalid = cited_source_numbers(answer, len(hits))

        warning = None
        if invalid:
            warning = f"The answer referenced unavailable sources: {invalid}."
        elif needs_citations and not valid:
            warning = "The answer could not be linked to a specific retrieved source."

        citations = [
            AnswerCitation(
                source_number=number,
                chunk_id=hit.chunk.chunk_id,
                title=hit.chunk.title,
                printed_page=hit.chunk.source.printed_page,
                physical_page=hit.chunk.source.physical_page,
            )
            for number, hit in enumerate(hits, start=1)
        ]
        return AssistantReply(
            query=response.query,
            answer=answer,
            hits=hits,
            citations=citations,
            context=context,
            model=self.model,
            retrieval_mode=mode,
            cited_source_numbers=valid,
            citation_repair_attempted=repair_attempted,
            eligibility_repair_attempted=eligibility_repair_attempted,
            citation_warning=warning,
        )

    @staticmethod
    def _deduplicate_hits(hits: list[RetrievalHit]) -> list[RetrievalHit]:
        unique: list[RetrievalHit] = []
        seen: set[str] = set()
        for hit in hits:
            if hit.chunk.chunk_id not in seen:
                unique.append(hit)
                seen.add(hit.chunk.chunk_id)
        return unique
