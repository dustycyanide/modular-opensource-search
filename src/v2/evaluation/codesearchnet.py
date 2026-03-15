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
        error_bucket_limit: int = 10,
    ) -> None:
        self.run_query = run_query
        self.queries_path = queries_path
        self.top_k = top_k
        self.recall_k = recall_k
        self.max_queries = max_queries
        self.error_bucket_limit = max(1, error_bucket_limit)

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
                "error_buckets": _build_error_buckets([], limit=self.error_bucket_limit),
            }

        ndcg_scores: list[float] = []
        mrr_scores: list[float] = []
        recall_scores: list[float] = []
        latency_totals: dict[str, float] = {}
        query_diagnostics: list[dict[str, Any]] = []
        evaluated_queries = 0

        for query in queries:
            judged = annotations.get(query)
            if not judged:
                continue
            predictions, latencies = _run_query(self.run_query, query, max(self.top_k, self.recall_k))
            predicted_ids = [_doc_id_from_evidence(item) for item in predictions]
            top_k_predictions = predicted_ids[: self.top_k]
            recall_predictions = predicted_ids[: self.recall_k]

            ndcg = _ndcg_at_k(predicted_ids, judged, self.top_k)
            mrr = _mrr_at_k(predicted_ids, judged, self.top_k)
            recall = _recall_at_k(predicted_ids, judged, self.recall_k)

            ndcg_scores.append(ndcg)
            mrr_scores.append(mrr)
            recall_scores.append(recall)
            for stage, value in latencies.items():
                latency_totals[stage] = latency_totals.get(stage, 0.0) + value

            missing_relevant_ids, false_positive_ids = _query_errors(
                judged=judged,
                top_k_predictions=top_k_predictions,
                recall_predictions=recall_predictions,
            )
            query_diagnostics.append(
                {
                    "query": query,
                    "ndcg": ndcg,
                    "mrr": mrr,
                    "recall": recall,
                    "first_relevant_rank": _first_relevant_rank(top_k_predictions, judged),
                    "relevant_count": len([doc_id for doc_id, rel in judged.items() if rel > 0]),
                    "missing_relevant_count": len(missing_relevant_ids),
                    "false_positive_count": len(false_positive_ids),
                    "missing_relevant_ids": missing_relevant_ids,
                    "false_positive_ids": false_positive_ids,
                    "top_predicted_ids": top_k_predictions,
                }
            )
            evaluated_queries += 1

        if evaluated_queries == 0:
            return {
                "query_count": 0,
                ndcg_key: 0.0,
                mrr_key: 0.0,
                recall_key: 0.0,
                "latency_ms": {},
                "error_buckets": _build_error_buckets([], limit=self.error_bucket_limit),
            }

        return {
            "query_count": evaluated_queries,
            ndcg_key: _safe_mean(ndcg_scores),
            mrr_key: _safe_mean(mrr_scores),
            recall_key: _safe_mean(recall_scores),
            "queries_with_any_relevant_hit": sum(1 for value in mrr_scores if value > 0.0),
            "queries_with_zero_hits": sum(1 for row in query_diagnostics if not row["top_predicted_ids"]),
            "latency_ms": {
                stage: value / evaluated_queries for stage, value in sorted(latency_totals.items())
            },
            "error_buckets": _build_error_buckets(query_diagnostics, limit=self.error_bucket_limit),
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
            current = annotations[query].get(doc_id)
            if current is None or relevance > current:
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


def _first_relevant_rank(predicted_ids: list[str], judged: dict[str, int]) -> int | None:
    for rank, doc_id in enumerate(predicted_ids, start=1):
        if judged.get(doc_id, 0) > 0:
            return rank
    return None


def _query_errors(
    *,
    judged: dict[str, int],
    top_k_predictions: list[str],
    recall_predictions: list[str],
) -> tuple[list[str], list[str]]:
    relevant_ids = {doc_id for doc_id, rel in judged.items() if rel > 0}
    retrieved_recall = set(recall_predictions)
    missing_relevant = sorted(relevant_ids - retrieved_recall)

    false_positives: list[str] = []
    for doc_id in top_k_predictions:
        relevance = judged.get(doc_id)
        if relevance is None:
            continue
        if relevance <= 0:
            false_positives.append(doc_id)
    return missing_relevant, false_positives


def _build_error_buckets(query_diagnostics: list[dict[str, Any]], *, limit: int) -> dict[str, Any]:
    missed_by_doc: dict[str, int] = {}
    false_positive_by_doc: dict[str, int] = {}
    top_missed_queries: list[dict[str, Any]] = []
    top_false_positive_queries: list[dict[str, Any]] = []

    for row in query_diagnostics:
        missing_ids = row.get("missing_relevant_ids", [])
        false_positive_ids = row.get("false_positive_ids", [])
        if not isinstance(missing_ids, list) or not isinstance(false_positive_ids, list):
            continue

        for doc_id in missing_ids:
            missed_by_doc[doc_id] = missed_by_doc.get(doc_id, 0) + 1
        for doc_id in false_positive_ids:
            false_positive_by_doc[doc_id] = false_positive_by_doc.get(doc_id, 0) + 1

        if missing_ids:
            top_missed_queries.append(
                {
                    "query": row.get("query"),
                    "missing_relevant_count": len(missing_ids),
                    "relevant_count": row.get("relevant_count", 0),
                    "top_predicted_ids": row.get("top_predicted_ids", [])[:3],
                    "missing_relevant_ids": missing_ids[:5],
                }
            )

        if false_positive_ids:
            top_false_positive_queries.append(
                {
                    "query": row.get("query"),
                    "false_positive_count": len(false_positive_ids),
                    "false_positive_ids": false_positive_ids[:5],
                    "top_predicted_ids": row.get("top_predicted_ids", [])[:3],
                }
            )

    top_missed_queries.sort(
        key=lambda item: (
            -int(item.get("missing_relevant_count", 0)),
            -int(item.get("relevant_count", 0)),
            str(item.get("query", "")),
        )
    )
    top_false_positive_queries.sort(
        key=lambda item: (
            -int(item.get("false_positive_count", 0)),
            str(item.get("query", "")),
        )
    )

    return {
        "top_missed_queries": top_missed_queries[:limit],
        "top_false_positive_queries": top_false_positive_queries[:limit],
        "common_missed_doc_ids": _top_doc_counts(missed_by_doc, limit=limit),
        "common_false_positive_doc_ids": _top_doc_counts(false_positive_by_doc, limit=limit),
    }


def _top_doc_counts(counts: dict[str, int], *, limit: int) -> list[dict[str, Any]]:
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [{"doc_id": doc_id, "count": count} for doc_id, count in ranked[:limit]]
