from __future__ import annotations

from collections import defaultdict

from ..contracts import QuerySpec, ScoredChunk


class ReciprocalRankFusion:
    def __init__(self, *, k: int = 60, max_candidates: int = 200) -> None:
        self.k = k
        self.max_candidates = max_candidates

    def fuse(self, ranked_lists, top_k: int):
        aggregate_scores: dict[str, float] = defaultdict(float)
        item_by_key: dict[str, ScoredChunk] = {}
        reasons_by_key: dict[str, list[str]] = defaultdict(list)

        for ranked in ranked_lists:
            for rank, item in enumerate(ranked, start=1):
                key = _chunk_key(item)
                aggregate_scores[key] += 1.0 / (self.k + rank)
                if key not in item_by_key:
                    item_by_key[key] = item
                for reason in item.reasons:
                    if reason not in reasons_by_key[key]:
                        reasons_by_key[key].append(reason)

        fused: list[ScoredChunk] = []
        for key, score in aggregate_scores.items():
            base = item_by_key[key]
            fused.append(
                ScoredChunk(
                    chunk=base.chunk,
                    score=score,
                    source="rrf",
                    reasons=tuple(reasons_by_key[key]) + ("rrf_fusion",),
                )
            )

        fused.sort(key=lambda item: item.score, reverse=True)
        limit = min(max(top_k * 4, top_k), self.max_candidates)
        return fused[:limit]


class HeuristicEvidenceReranker:
    def rerank(self, query: QuerySpec, chunks):
        query_tokens = {
            token
            for token in query.text.lower().split()
            if len(token) >= 3
        }
        reranked: list[ScoredChunk] = []
        for item in chunks:
            path = item.chunk.path.lower()
            content = item.chunk.content.lower()
            score = item.score
            reasons = list(item.reasons)

            if item.chunk.language != "Text":
                score += 0.08
                reasons.append("source_code_boost")
            if any(token in path for token in query_tokens):
                score += 0.06
                reasons.append("path_query_overlap")
            if "def " in content or "class " in content or "func " in content:
                score += 0.05
                reasons.append("definition_like_boost")
            if "/examples/" in f"/{path}":
                score += 0.20
                reasons.append("examples_boost")
            if "/test" in f"/{path}" or "/tests/" in f"/{path}":
                score += 0.15
                reasons.append("tests_boost")
            if "/docs/" in f"/{path}" or path.endswith("readme.md"):
                score += 0.08
                reasons.append("docs_boost")
            if path.endswith(("readme.md", ".md")) and item.chunk.language == "Text":
                score -= 0.04
                reasons.append("docs_only_penalty")
            if path.endswith(("docker-compose.yml", "docker-compose.yaml", ".github/workflows/ci.yml")):
                score += 0.10
                reasons.append("runnable_signal_boost")

            reranked.append(
                ScoredChunk(
                    chunk=item.chunk,
                    score=score,
                    source="heuristic_reranker",
                    reasons=tuple(reasons),
                )
            )

        reranked.sort(key=lambda item: item.score, reverse=True)
        return reranked


def _chunk_key(item: ScoredChunk) -> str:
    chunk = item.chunk
    return f"{chunk.repo}:{chunk.path}:{chunk.start_line}:{chunk.end_line}"
