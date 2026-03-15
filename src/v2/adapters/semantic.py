from __future__ import annotations

from ..contracts import QuerySpec, ScoredChunk
from .embedding_index import EmbeddingConfig, EmbeddingIndex


class EmbeddingSemanticRetriever:
    def __init__(
        self,
        *,
        model_name: str = "BAAI/bge-base-en-v1.5",
        candidate_multiplier: int = 5,
    ) -> None:
        self.candidate_multiplier = candidate_multiplier
        self.index = EmbeddingIndex(EmbeddingConfig(model_name=model_name))

    def retrieve(self, query: QuerySpec, corpus):
        if not corpus:
            return []

        self.index.build([_semantic_text(chunk) for chunk in corpus])
        top_k = max(query.top_k * self.candidate_multiplier, query.top_k)

        out: list[ScoredChunk] = []
        for doc_index, score in self.index.search(query.text, top_k=top_k):
            out.append(
                ScoredChunk(
                    chunk=corpus[doc_index],
                    score=score,
                    source="embedding_semantic",
                    reasons=("semantic_embedding_match",),
                )
            )
        return out


def _semantic_text(chunk) -> str:
    parts = [chunk.path, chunk.language, chunk.content]
    return "\n".join(part for part in parts if part)
