"""Embedding provider boundary and deterministic offline fallback."""

from __future__ import annotations

import hashlib
import re
from typing import Protocol

import numpy as np
from numpy.typing import NDArray


class EmbeddingProvider(Protocol):
    name: str
    dimensions: int

    def embed_texts(self, texts: list[str]) -> NDArray[np.float32]: ...


class HashingEmbeddingProvider:
    """Local feature-hashing vectors for plumbing tests, not learned semantics."""

    name = "local-hashing-word-char-v1"

    def __init__(self, dimensions: int = 1024) -> None:
        if dimensions < 64:
            raise ValueError("dimensions must be at least 64")
        self.dimensions = dimensions

    def embed_texts(self, texts: list[str]) -> NDArray[np.float32]:
        matrix = np.zeros((len(texts), self.dimensions), dtype=np.float32)
        for row, text in enumerate(texts):
            for feature, weight in self._features(text):
                digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
                value = int.from_bytes(digest, "little")
                column = value % self.dimensions
                sign = 1.0 if value & (1 << 63) else -1.0
                matrix[row, column] += sign * weight
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        np.divide(matrix, norms, out=matrix, where=norms != 0)
        return matrix

    @staticmethod
    def _features(text: str) -> list[tuple[str, float]]:
        normalized = " ".join(re.findall(r"[a-z0-9]+", text.casefold()))
        words = normalized.split()
        features = [(f"w:{word}", 1.0) for word in words]
        features.extend(
            (f"b:{first}_{second}", 1.25)
            for first, second in zip(words, words[1:])
        )
        compact = normalized.replace(" ", "_")
        features.extend(
            (f"c:{compact[index:index + 3]}", 0.2)
            for index in range(max(0, len(compact) - 2))
        )
        return features
