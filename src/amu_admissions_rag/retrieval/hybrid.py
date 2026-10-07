"""In-memory hybrid retrieval mirroring the PostgreSQL RRF design."""

from __future__ import annotations

import re
from collections.abc import Sequence

import numpy as np

from amu_admissions_rag.models import (
    ChunkType,
    CourseCandidate,
    CourseRecord,
    CourseCorpus,
    CourseDiscoveryResponse,
    ProgramLevel,
    IndexCorpus,
    RetrievalHit,
    RetrievalResponse,
)
from amu_admissions_rag.query_processing import QueryProcessor
from amu_admissions_rag.retrieval.bm25 import BM25Index, tokenize
from amu_admissions_rag.retrieval.embedding import (
    EmbeddingProvider,
    HashingEmbeddingProvider,
)


class HybridRetriever:
    """Fuse BM25 and vector ranks, then hydrate linked course parents."""

    def __init__(
        self,
        index_corpus: IndexCorpus,
        course_corpus: CourseCorpus,
        *,
        embedding_provider: EmbeddingProvider | None = None,
        query_processor: QueryProcessor | None = None,
        rrf_k: int = 60,
    ) -> None:
        if index_corpus.document.document_id != course_corpus.document.document_id:
            raise ValueError("index and course corpora must belong to the same document")
        self.index_corpus = index_corpus
        self.course_parents = {course.record_id: course for course in course_corpus.courses}
        self.embedding_provider = embedding_provider or HashingEmbeddingProvider()
        self.query_processor = query_processor or QueryProcessor()
        self.rrf_k = rrf_k
        self._documents = [f"{chunk.title}\n{chunk.text}" for chunk in index_corpus.chunks]
        self._bm25 = BM25Index(self._documents)
        self._vectors = self.embedding_provider.embed_texts(self._documents)

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        candidate_limit: int = 40,
    ) -> RetrievalResponse:
        if limit < 1 or candidate_limit < 1:
            raise ValueError("limit and candidate_limit must be positive")
        analysis = self.query_processor.analyze(query)
        lexical_scores = self._bm25.scores(analysis.expanded_query)
        query_vector = self.embedding_provider.embed_texts([analysis.expanded_query])[0]
        vector_scores = self._vectors @ query_vector

        lexical_order = self._rank(lexical_scores, candidate_limit, positive_only=True)
        vector_order = self._rank(vector_scores, candidate_limit, positive_only=True)
        lexical_ranks = {index: rank for rank, index in enumerate(lexical_order, start=1)}
        vector_ranks = {index: rank for rank, index in enumerate(vector_order, start=1)}

        candidate_indexes = set(lexical_order) | set(vector_order)
        scored: list[tuple[float, int, float, float]] = []
        for index in candidate_indexes:
            fused_score = 0.0
            if index in lexical_ranks:
                fused_score += 1 / (self.rrf_k + lexical_ranks[index])
            if index in vector_ranks:
                fused_score += 1 / (self.rrf_k + vector_ranks[index])
            chunk = self.index_corpus.chunks[index]
            intent_boost = 0.0
            if chunk.field_name in analysis.preferred_fields:
                intent_boost = 1.25 / (self.rrf_k + 1)
                fused_score += intent_boost
            exact_value_boost = 0.0
            field_is_relevant = (
                not analysis.preferred_fields
                or chunk.field_name in analysis.preferred_fields
            )
            if field_is_relevant and self._has_exact_structured_value(
                analysis.expanded_query,
                chunk.text,
            ):
                exact_value_boost = 0.5 / (self.rrf_k + 1)
                fused_score += exact_value_boost
            scored.append((fused_score, index, intent_boost, exact_value_boost))

        scored.sort(
            key=lambda item: (
                item[0],
                lexical_scores[item[1]],
                float(vector_scores[item[1]]),
            ),
            reverse=True,
        )
        hits: list[RetrievalHit] = []
        hydrated: dict[str, CourseRecord] = {}
        for fused_score, index, intent_boost, exact_value_boost in scored[:limit]:
            chunk = self.index_corpus.chunks[index]
            hits.append(
                RetrievalHit(
                    chunk=chunk,
                    fused_score=fused_score,
                    lexical_score=lexical_scores[index],
                    vector_score=float(vector_scores[index]),
                    lexical_rank=lexical_ranks.get(index),
                    vector_rank=vector_ranks.get(index),
                    intent_boost=intent_boost,
                    exact_value_boost=exact_value_boost,
                )
            )
            parent = self.course_parents.get(chunk.parent_record_id)
            if parent is not None:
                hydrated[parent.record_id] = parent
        return RetrievalResponse(
            query=analysis,
            hits=hits,
            course_parents=hydrated,
            embedding_provider=self.embedding_provider.name,
        )

    def discover_courses(
        self,
        query: str,
        *,
        limit: int = 5,
        evidence_per_course: int = 2,
    ) -> CourseDiscoveryResponse:
        """Rank content-rich course profiles and attach citable child evidence."""

        if limit < 1 or evidence_per_course < 1:
            raise ValueError("limit and evidence_per_course must be positive")
        analysis = self.query_processor.analyze(query)
        profile_indexes = [
            index
            for index, chunk in enumerate(self.index_corpus.chunks)
            if chunk.chunk_type is ChunkType.COURSE_OVERVIEW
        ]
        lexical_scores = self._bm25.scores(analysis.expanded_query)
        query_vector = self.embedding_provider.embed_texts([analysis.expanded_query])[0]
        vector_scores = self._vectors @ query_vector
        lexical_order = sorted(
            profile_indexes,
            key=lambda index: lexical_scores[index],
            reverse=True,
        )
        lexical_order = [index for index in lexical_order if lexical_scores[index] > 0]
        vector_order = sorted(
            profile_indexes,
            key=lambda index: vector_scores[index],
            reverse=True,
        )
        vector_order = [index for index in vector_order if vector_scores[index] > 0]
        lexical_ranks = {index: rank for rank, index in enumerate(lexical_order, start=1)}
        vector_ranks = {index: rank for rank, index in enumerate(vector_order, start=1)}

        ranked_profiles: list[RetrievalHit] = []
        for index in set(lexical_order) | set(vector_order):
            score = 0.0
            if index in lexical_ranks:
                score += 1 / (self.rrf_k + lexical_ranks[index])
            if index in vector_ranks:
                score += 1 / (self.rrf_k + vector_ranks[index])
            ranked_profiles.append(
                RetrievalHit(
                    chunk=self.index_corpus.chunks[index],
                    fused_score=score,
                    lexical_score=lexical_scores[index],
                    vector_score=float(vector_scores[index]),
                    lexical_rank=lexical_ranks.get(index),
                    vector_rank=vector_ranks.get(index),
                )
            )
        ranked_profiles.sort(
            key=lambda hit: (
                hit.fused_score,
                hit.lexical_score,
                hit.vector_score,
            ),
            reverse=True,
        )

        evidence_response = self.search(
            query,
            limit=len(self.index_corpus.chunks),
            candidate_limit=len(self.index_corpus.chunks),
        )
        preferred_levels = self._preferred_target_levels(analysis.expanded_query)
        candidate_profiles: list[
            tuple[float, float, RetrievalHit, CourseRecord]
        ] = []
        for profile in ranked_profiles:
            parent = self.course_parents.get(profile.chunk.parent_record_id)
            if parent is None:
                continue
            level_boost = 0.0
            if parent.program_level in preferred_levels:
                level_boost = 0.5 / (self.rrf_k + 1)
            candidate_profiles.append(
                (profile.fused_score + level_boost, level_boost, profile, parent)
            )
        candidate_profiles.sort(key=lambda item: item[0], reverse=True)

        candidates: list[CourseCandidate] = []
        for score, level_boost, profile, parent in candidate_profiles[:limit]:
            evidence = [
                hit
                for hit in evidence_response.hits
                if hit.chunk.parent_record_id == parent.record_id
                and hit.chunk.chunk_type is not ChunkType.COURSE_OVERVIEW
            ]
            if analysis.preferred_fields:
                evidence.sort(
                    key=lambda hit: (
                        hit.chunk.field_name in analysis.preferred_fields,
                        hit.fused_score,
                    ),
                    reverse=True,
                )
            candidates.append(
                CourseCandidate(
                    course=parent,
                    score=score,
                    program_level_boost=level_boost,
                    profile=profile,
                    evidence=evidence[:evidence_per_course],
                )
            )
        return CourseDiscoveryResponse(
            query=analysis,
            candidates=candidates,
            embedding_provider=self.embedding_provider.name,
        )

    @staticmethod
    def _preferred_target_levels(query: str) -> set[ProgramLevel]:
        normalized = " ".join(tokenize(query))
        bachelor_pattern = re.compile(
            r"\b(?:completed|have|hold|earned|graduated)\b.{0,30}\b"
            r"(?:bachelor|bsc|bcom|btech|bca|bba|ba|be|mbbs|bums)\b"
        )
        master_pattern = re.compile(
            r"\b(?:completed|have|hold|earned|graduated)\b.{0,30}\b"
            r"(?:master|msc|mcom|mtech|mca|mba|ma|msw)\b"
        )
        school_pattern = re.compile(
            r"\b(?:passed|completed|have)\b.{0,30}\b"
            r"(?:class 12|12th|senior secondary)\b"
        )
        if master_pattern.search(normalized):
            return {ProgramLevel.RESEARCH}
        if bachelor_pattern.search(normalized):
            return {ProgramLevel.POSTGRADUATE}
        if school_pattern.search(normalized):
            return {ProgramLevel.UNDERGRADUATE, ProgramLevel.DIPLOMA}
        return set()

    @staticmethod
    def _has_exact_structured_value(query: str, chunk_text: str) -> bool:
        normalized_query = " ".join(tokenize(query))
        context_keys = {
            "course",
            "expanded course name",
            "faculty",
            "programme level",
            "record type",
            "field",
            "table",
            "table row",
        }
        for line in chunk_text.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            if " ".join(tokenize(key)) in context_keys:
                continue
            value = value.strip()
            normalized_value = " ".join(tokenize(value))
            if normalized_value and normalized_value in normalized_query:
                return True
        return False

    @staticmethod
    def _rank(
        scores: Sequence[float],
        limit: int,
        *,
        positive_only: bool,
    ) -> list[int]:
        indexes = range(len(scores))
        ordered = sorted(indexes, key=lambda index: scores[index], reverse=True)
        if positive_only:
            ordered = [index for index in ordered if scores[index] > 0]
        return ordered[:limit]
