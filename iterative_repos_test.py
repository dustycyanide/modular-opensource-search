#!/usr/bin/env python3
"""Iterative small-sample test for capability-search viability.

Flow:
1. Clone up to 5 small OSS repositories (depth=1).
2. Ingest one-by-one into capability index.
3. After each ingest, run fixed top-K queries.
4. Emit a compact JSON report with rough precision@k.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from capability_index import init_db, search_cards, upsert_repo_and_cards


ROOT = Path(__file__).resolve().parent
REPOS_DIR = ROOT / "repos"
DB_PATH = ROOT / "data" / "capabilities_iterative.db"
REPORT_PATH = ROOT / "data" / "iterative_report.json"


REPOS = [
    {"name": "OCRmyPDF", "url": "https://github.com/ocrmypdf/OCRmyPDF.git"},
    {"name": "requests", "url": "https://github.com/psf/requests.git"},
    {"name": "flask", "url": "https://github.com/pallets/flask.git"},
    {"name": "click", "url": "https://github.com/pallets/click.git"},
    {"name": "pytesseract", "url": "https://github.com/madmaze/pytesseract.git"},
]


QUERIES = [
    {
        "name": "ocr_pipeline",
        "query": "python ocr document pipeline async",
        "expected_capabilities": {"ocr_processing", "document_ingestion_pipeline", "async_processing_engine"},
        "expected_repos": {"OCRmyPDF", "pytesseract"},
    },
    {
        "name": "api_service",
        "query": "python api service",
        "expected_capabilities": {"api_service"},
        "expected_repos": {"flask"},
    },
    {
        "name": "cli_tooling",
        "query": "python cli command tooling",
        "expected_capabilities": {"cli_tooling"},
        "expected_repos": {"click", "flask", "OCRmyPDF"},
    },
]


@dataclass
class QuerySnapshot:
    name: str
    query: str
    top_k: int
    precision_at_k: float
    repo_precision_at_k: float
    expected_repo_coverage: float
    results: list[dict]


@dataclass
class IterationSnapshot:
    repos_indexed: list[str]
    cards_added_for_latest_repo: int
    query_snapshots: list[QuerySnapshot]


def run(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def clone_if_missing(repo_name: str, repo_url: str) -> Path:
    repo_path = REPOS_DIR / repo_name
    if repo_path.exists():
        return repo_path
    run(["git", "clone", "--depth", "1", repo_url, str(repo_path)])
    return repo_path


def to_result_dict(row) -> dict:
    evidence = json.loads(row["evidence_json"] or "[]")
    return {
        "repo": row["repo_name"],
        "title": row["title"],
        "capability": row["capability_name"],
        "confidence": round(float(row["confidence"]), 3),
        "license": row["license"],
        "language": row["primary_language"],
        "evidence_preview": evidence[:3],
    }


def compute_precision(results: list[dict], expected_caps: set[str], k: int) -> float:
    if k <= 0 or not results:
        return 0.0
    denom = min(k, len(results))
    relevant = 0
    for result in results[:denom]:
        if result["capability"] in expected_caps:
            relevant += 1
    return round(relevant / denom, 3)


def compute_repo_precision(results: list[dict], expected_repos: set[str], k: int) -> float:
    if k <= 0 or not results:
        return 0.0
    denom = min(k, len(results))
    relevant = 0
    for result in results[:denom]:
        if result["repo"] in expected_repos:
            relevant += 1
    return round(relevant / denom, 3)


def compute_repo_coverage(results: list[dict], expected_repos: set[str], k: int) -> float:
    if not expected_repos:
        return 0.0
    seen = set()
    for result in results[:k]:
        if result["repo"] in expected_repos:
            seen.add(result["repo"])
    return round(len(seen) / len(expected_repos), 3)


def main() -> None:
    REPOS_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    init_db(DB_PATH)

    iterations: list[IterationSnapshot] = []
    indexed_repo_names: list[str] = []

    for repo in REPOS:
        repo_path = clone_if_missing(repo["name"], repo["url"])
        cards_added = upsert_repo_and_cards(DB_PATH, repo_path, repo["name"])
        indexed_repo_names.append(repo["name"])

        query_snapshots: list[QuerySnapshot] = []
        for query in QUERIES:
            rows = search_cards(DB_PATH, query["query"], 5)
            results = [to_result_dict(row) for row in rows]
            precision = compute_precision(results, query["expected_capabilities"], k=5)
            repo_precision = compute_repo_precision(results, query["expected_repos"], k=5)
            repo_coverage = compute_repo_coverage(results, query["expected_repos"], k=5)

            query_snapshots.append(
                QuerySnapshot(
                    name=query["name"],
                    query=query["query"],
                    top_k=5,
                    precision_at_k=precision,
                    repo_precision_at_k=repo_precision,
                    expected_repo_coverage=repo_coverage,
                    results=results,
                )
            )

        iterations.append(
            IterationSnapshot(
                repos_indexed=list(indexed_repo_names),
                cards_added_for_latest_repo=cards_added,
                query_snapshots=query_snapshots,
            )
        )

    report = {
        "db_path": str(DB_PATH),
        "repo_count": len(indexed_repo_names),
        "repos": indexed_repo_names,
        "queries": [q["name"] for q in QUERIES],
        "iterations": [
            {
                "repos_indexed": iteration.repos_indexed,
                "cards_added_for_latest_repo": iteration.cards_added_for_latest_repo,
                "query_snapshots": [asdict(qs) for qs in iteration.query_snapshots],
            }
            for iteration in iterations
        ],
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Wrote iterative report: {REPORT_PATH}")
    for iteration in iterations:
        repos_str = ", ".join(iteration.repos_indexed)
        print(f"\n=== Indexed: {repos_str} ===")
        for snapshot in iteration.query_snapshots:
            print(
                f"{snapshot.name}: precision@5={snapshot.precision_at_k} "
                f"repo_precision@5={snapshot.repo_precision_at_k} "
                f"repo_coverage={snapshot.expected_repo_coverage} "
                f"query='{snapshot.query}'"
            )
            for idx, result in enumerate(snapshot.results[:3], start=1):
                print(
                    f"  [{idx}] {result['repo']} | {result['capability']} "
                    f"| conf={result['confidence']}"
                )


if __name__ == "__main__":
    main()
