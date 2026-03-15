from __future__ import annotations

from dataclasses import dataclass

from fastembed import TextEmbedding
import numpy as np


@dataclass(frozen=True)
class EmbeddingConfig:
    model_name: str = "BAAI/bge-base-en-v1.5"


class EmbeddingIndex:
    def __init__(self, config: EmbeddingConfig | None = None) -> None:
        self.config = config or EmbeddingConfig()
        self.model = TextEmbedding(model_name=self.config.model_name, lazy_load=True)
        self._vectors: np.ndarray | None = None

    def build(self, texts: list[str]) -> None:
        if not texts:
            self._vectors = None
            return
        vectors = np.vstack(list(self.model.passage_embed(texts))).astype("float32")
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        self._vectors = vectors / np.clip(norms, 1e-12, None)

    def search(self, query_text: str, *, top_k: int) -> list[tuple[int, float]]:
        if self._vectors is None or top_k <= 0:
            return []

        query_vector = np.asarray(next(self.model.query_embed([query_text])), dtype="float32")
        query_vector = query_vector / max(np.linalg.norm(query_vector), 1e-12)
        scores = self._vectors @ query_vector

        limit = min(top_k, len(scores))
        candidate_indexes = np.argpartition(scores, -limit)[-limit:]
        ranked = sorted(
            ((int(index), float(scores[index])) for index in candidate_indexes),
            key=lambda item: item[1],
            reverse=True,
        )
        return ranked
