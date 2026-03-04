from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlparse

from ..contracts import EvidenceItem


class CodeSearchNetEvaluator:
    def __init__(
        self,
        *,
        run_query: Callable[[str, int], list[EvidenceItem] | tuple[list[EvidenceItem], dict[str, float]]],
        queries_path: str | None = None,
        top_k: int = 10,
        recall_k: int = 50,
        max_queries: int = 20,
    ) -> None:
        self.run_query = run_query
        self.queries_path = queries_path
        self.top_k = top_k
        self.recall_k = recall_k
        self.max_queries = max_queries

    def evaluate(self, annotations_path: str) -> dict[str, Any]:
        annotations = _load_annotations(annotations_path)
        queries = _load_queries(self.queries_path, annotations)
        if self.max_queries > 0:
            queries = queries[: self.max_queries]

        ndcg_key = f"ndcg@{self.top_k}"
        mrr_key = f"mrr@{self.top_k}"
        recall_key = f"recall@{self.recall_k}"

        if not queries:
            return {
                "query_count": 0,
                ndcg_key: 0.0,
                mrr_key: 0.0,
                recall_key: 0.0,
                "latency_ms": {},
            }

        ndcg_scores: list[float] = []
        mrr_scores: list[float] = []
        recall_scores: list[float] = []
        latency_totals: dict[str, float] = {}
        evaluated_queries = 0

        for query in queries:
            judged = annotations.get(query)
            if not judged:
                continue
            predictions, latencies = _run_query(self.run_query, query, max(self.top_k, self.recall_k))
            predicted_ids = [_doc_id_from_evidence(item) for item in predictions]

            ndcg_scores.append(_ndcg_at_k(predicted_ids, judged, self.top_k))
            mrr_scores.append(_mrr_at_k(predicted_ids, judged, self.top_k))
            recall_scores.append(_recall_at_k(predicted_ids, judged, self.recall_k))
            for stage, value in latencies.items():
                latency_totals[stage] = latency_totals.get(stage, 0.0) + value
            evaluated_queries += 1

        if evaluated_queries == 0:
            return {
                "query_count": 0,
                ndcg_key: 0.0,
                mrr_key: 0.0,
                recall_key: 0.0,
                "latency_ms": {},
            }

        return {
            "query_count": evaluated_queries,
            ndcg_key: _safe_mean(ndcg_scores),
            mrr_key: _safe_mean(mrr_scores),
            recall_key: _safe_mean(recall_scores),
            "latency_ms": {
                stage: value / evaluated_queries for stage, value in sorted(latency_totals.items())
            },
        }


def _run_query(
    run_query: Callable[[str, int], list[EvidenceItem] | tuple[list[EvidenceItem], dict[str, float]]],
    query: str,
    top_k: int,
) -> tuple[list[EvidenceItem], dict[str, float]]:
    result = run_query(query, top_k)
    if isinstance(result, tuple) and len(result) == 2:
        predictions, latencies = result
        if isinstance(predictions, list) and isinstance(latencies, dict):
            return predictions, {str(k): float(v) for k, v in latencies.items()}
    if isinstance(result, list):
        return result, {}
    raise TypeError("run_query must return list[EvidenceItem] or (list[EvidenceItem], dict[str, float])")


def _load_annotations(path: str) -> dict[str, dict[str, int]]:
    annotations: dict[str, dict[str, int]] = {}
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            query = (row.get("Query") or row.get("query") or "").strip()
            url = (row.get("GitHubUrl") or row.get("URL") or row.get("url") or "").strip()
            relevance_raw = (row.get("Relevance") or row.get("relevance") or "0").strip()
            if not query or not url:
                continue
            try:
                relevance = int(float(relevance_raw))
            except ValueError:
                relevance = 0

            doc_id = _doc_id_from_url(url)
            if not doc_id:
                continue
            if query not in annotations:
                annotations[query] = {}
            current = annotations[query].get(doc_id, 0)
            if relevance > current:
                annotations[query][doc_id] = relevance
    return annotations


def _load_queries(
    queries_path: str | None,
    annotations: dict[str, dict[str, int]],
) -> list[str]:
    if not queries_path:
        return list(annotations.keys())

    with Path(queries_path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        out: list[str] = []
        for row in reader:
            query = (row.get("Query") or row.get("query") or "").strip()
            if query:
                out.append(query)
    return out


def _doc_id_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 5:
        return None
    if parts[2] != "blob":
        return None
    owner, repo = parts[0], parts[1]
    file_path = "/".join(parts[4:])
    if not file_path:
        return None
    return f"{owner.lower()}/{repo.lower()}/{file_path.lower()}"


def _doc_id_from_evidence(item: EvidenceItem) -> str:
    if item.permalink:
        from_url = _doc_id_from_url(item.permalink)
        if from_url:
            return from_url
    return f"{item.repo.lower()}/{item.path.lower().lstrip('/')}"


def _mrr_at_k(predicted_ids: list[str], judged: dict[str, int], k: int) -> float:
    for rank, doc_id in enumerate(predicted_ids[:k], start=1):
        if judged.get(doc_id, 0) > 0:
            return 1.0 / rank
    return 0.0


def _recall_at_k(predicted_ids: list[str], judged: dict[str, int], k: int) -> float:
    relevant = {doc_id for doc_id, relevance in judged.items() if relevance > 0}
    if not relevant:
        return 0.0
    retrieved = set(predicted_ids[:k])
    return len(relevant.intersection(retrieved)) / len(relevant)


def _ndcg_at_k(predicted_ids: list[str], judged: dict[str, int], k: int) -> float:
    gains = [judged.get(doc_id, 0) for doc_id in predicted_ids[:k]]
    dcg = _dcg(gains)
    ideal_gains = sorted((value for value in judged.values() if value > 0), reverse=True)[:k]
    idcg = _dcg(ideal_gains)
    if idcg <= 0.0:
        return 0.0
    return dcg / idcg


def _dcg(gains: Iterable[int]) -> float:
    score = 0.0
    for index, gain in enumerate(gains, start=1):
        if gain <= 0:
            continue
        score += (2**gain - 1) / math.log2(index + 1)
    return score


def _safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)
