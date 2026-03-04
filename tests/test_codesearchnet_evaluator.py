from pathlib import Path

from v2.contracts import EvidenceItem
from v2.evaluation.codesearchnet import CodeSearchNetEvaluator


def test_codesearchnet_evaluator_scores_relevant_hit(tmp_path: Path) -> None:
    annotations = tmp_path / "annotations.csv"
    annotations.write_text(
        "Language,Query,GitHubUrl,Relevance,Notes\n"
        "python,parse json,https://github.com/foo/bar/blob/abc123/src/parser.py#L1-L9,3,\n",
        encoding="utf-8",
    )

    def run_query(query: str, top_k: int):
        del query, top_k
        return [
            EvidenceItem(
                repo="foo/bar",
                commit_sha="def456",
                path="src/parser.py",
                start_line=10,
                end_line=20,
                snippet="def parse_json(data): ...",
                score=1.0,
                permalink="https://github.com/foo/bar/blob/def456/src/parser.py#L10-L20",
            )
        ]

    evaluator = CodeSearchNetEvaluator(run_query=run_query, max_queries=1)
    metrics = evaluator.evaluate(str(annotations))
    assert metrics["query_count"] == 1
    assert metrics["mrr@10"] == 1.0
    assert metrics["ndcg@10"] > 0.0


def test_codesearchnet_evaluator_collects_latency(tmp_path: Path) -> None:
    annotations = tmp_path / "annotations.csv"
    annotations.write_text(
        "Language,Query,GitHubUrl,Relevance,Notes\n"
        "python,parse json,https://github.com/foo/bar/blob/abc123/src/parser.py#L1-L9,3,\n",
        encoding="utf-8",
    )

    def run_query(query: str, top_k: int):
        del query, top_k
        return (
            [
                EvidenceItem(
                    repo="foo/bar",
                    commit_sha="abc123",
                    path="src/parser.py",
                    start_line=1,
                    end_line=9,
                    snippet="def parse_json(data): ...",
                    score=1.0,
                    permalink="https://github.com/foo/bar/blob/abc123/src/parser.py#L1-L9",
                )
            ],
            {"lexical": 2.0, "total": 5.0},
        )

    evaluator = CodeSearchNetEvaluator(run_query=run_query, max_queries=1)
    metrics = evaluator.evaluate(str(annotations))
    assert metrics["query_count"] == 1
    assert metrics["latency_ms"] == {"lexical": 2.0, "total": 5.0}
