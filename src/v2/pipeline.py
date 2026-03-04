from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Sequence

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
        evidence, _ = self.run_with_trace(query)
        return evidence

    def run_with_trace(self, query: QuerySpec) -> tuple[Sequence[EvidenceItem], dict[str, float]]:
        stage_ms: dict[str, float] = {}
        total_start = perf_counter()

        start = perf_counter()
        candidates = self.discoverer.discover(query)
        stage_ms["discover"] = _elapsed_ms(start)

        start = perf_counter()
        corpus = self.ingestor.ingest(candidates)
        stage_ms["ingest"] = _elapsed_ms(start)

        start = perf_counter()
        lexical_hits = self.lexical.retrieve(query, corpus)
        stage_ms["lexical"] = _elapsed_ms(start)

        start = perf_counter()
        semantic_hits = self.semantic.retrieve(query, corpus)
        stage_ms["semantic"] = _elapsed_ms(start)

        start = perf_counter()
        fused = self.fuser.fuse([lexical_hits, semantic_hits], top_k=query.top_k)
        stage_ms["fuse"] = _elapsed_ms(start)

        start = perf_counter()
        reranked = self.reranker.rerank(query, fused)

        stage_ms["rerank"] = _elapsed_ms(start)

        start = perf_counter()
        packaged = self.packager.package(query, reranked[: query.top_k])
        stage_ms["package"] = _elapsed_ms(start)
        stage_ms["total"] = _elapsed_ms(total_start)
        return packaged, stage_ms

    def evaluate(self, annotations_path: str) -> dict[str, Any]:
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
    def evaluate(self, annotations_path: str) -> dict[str, Any]:
        del annotations_path
        return {"query_count": 0, "ndcg@10": 0.0, "mrr@10": 0.0, "recall@50": 0.0}


def _elapsed_ms(start: float) -> float:
    return round((perf_counter() - start) * 1000.0, 4)
