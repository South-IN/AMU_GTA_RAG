"""Small dependency-free BM25 index for local retrieval and evaluation."""

from __future__ import annotations

import math
import re
from collections import Counter


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.casefold())


class BM25Index:
    def __init__(
        self,
        documents: list[str],
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.k1 = k1
        self.b = b
        self.term_frequencies = [Counter(tokenize(text)) for text in documents]
        self.document_lengths = [sum(counts.values()) for counts in self.term_frequencies]
        self.average_length = (
            sum(self.document_lengths) / len(self.document_lengths)
            if self.document_lengths
            else 0.0
        )
        document_frequency: Counter[str] = Counter()
        for counts in self.term_frequencies:
            document_frequency.update(counts.keys())
        document_count = len(documents)
        self.idf = {
            term: math.log(1 + (document_count - frequency + 0.5) / (frequency + 0.5))
            for term, frequency in document_frequency.items()
        }

    def scores(self, query: str) -> list[float]:
        query_terms = Counter(tokenize(query))
        results: list[float] = []
        for frequencies, length in zip(
            self.term_frequencies,
            self.document_lengths,
            strict=True,
        ):
            score = 0.0
            length_normalizer = 1 - self.b
            if self.average_length:
                length_normalizer += self.b * length / self.average_length
            for term, query_frequency in query_terms.items():
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                numerator = frequency * (self.k1 + 1)
                denominator = frequency + self.k1 * length_normalizer
                term_score = self.idf.get(term, 0.0) * numerator / denominator
                if query_frequency > 1:
                    term_score *= 1 + math.log(query_frequency)
                score += term_score
            results.append(score)
        return results
