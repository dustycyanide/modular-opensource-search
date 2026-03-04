from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .contracts import (
    Discoverer,
    Evaluator,
    EvidenceItem,
    EvidencePackager,
    Ingestor,
    LexicalRetriever,
    QuerySpec,
    RankFuser,
    Reranker,
    ScoredChunk,
    SemanticRetriever,
)


@dataclass
class OrchestrationPipeline:
    discoverer: Discoverer
    ingestor: Ingestor
    lexical: LexicalRetriever
    semantic: SemanticRetriever
    fuser: RankFuser
    reranker: Reranker
    packager: EvidencePackager
    evaluator: Evaluator | None = None

    def run(self, query: QuerySpec) -> Sequence[EvidenceItem]:
        candidates = self.discoverer.discover(query)
        corpus = self.ingestor.ingest(candidates)
        lexical_hits = self.lexical.retrieve(query, corpus)
        semantic_hits = self.semantic.retrieve(query, corpus)
        fused = self.fuser.fuse([lexical_hits, semantic_hits], top_k=query.top_k)
        reranked = self.reranker.rerank(query, fused)
        return self.packager.package(query, reranked[: query.top_k])

    def evaluate(self, annotations_path: str) -> dict[str, float | int]:
        if self.evaluator is None:
            raise RuntimeError("Evaluator is not configured for this pipeline")
        return self.evaluator.evaluate(annotations_path)


class NoOpDiscoverer:
    def discover(self, query: QuerySpec):
        return []


class NoOpIngestor:
    def ingest(self, candidates):
        return []


class NoOpRetriever:
    def retrieve(self, query: QuerySpec, corpus):
        return []


class NoOpFuser:
    def fuse(self, ranked_lists, top_k: int):
        del top_k
        flattened: list[ScoredChunk] = []
        for item in ranked_lists:
            flattened.extend(item)
        return flattened


class NoOpReranker:
    def rerank(self, query: QuerySpec, chunks):
        del query
        return chunks


class NoOpPackager:
    def package(self, query: QuerySpec, chunks):
        del query, chunks
        return []


class NoOpEvaluator:
    def evaluate(self, annotations_path: str) -> dict[str, float | int]:
        del annotations_path
        return {"query_count": 0, "ndcg@10": 0.0, "mrr@10": 0.0, "recall@50": 0.0}
