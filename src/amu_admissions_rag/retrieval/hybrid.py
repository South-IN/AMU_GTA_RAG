"""In-memory hybrid retrieval mirroring the PostgreSQL RRF design."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from amu_admissions_rag.models import (
    CourseRecord,
    CourseCorpus,
    IndexCorpus,
    RetrievalHit,
    RetrievalResponse,
)
from amu_admissions_rag.query_processing import QueryProcessor
from amu_admissions_rag.retrieval.bm25 import BM25Index
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
        scored: list[tuple[float, int, float]] = []
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
            scored.append((fused_score, index, intent_boost))

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
        for fused_score, index, intent_boost in scored[:limit]:
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
