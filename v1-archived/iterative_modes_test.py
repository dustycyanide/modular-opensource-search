#!/usr/bin/env python3
"""Compare lexical, semantic, and hybrid retrieval modes iteratively."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from capability_index import init_db, search_cards, upsert_repo_and_cards


ROOT = Path(__file__).resolve().parent
REPOS_DIR = ROOT / "repos"
DB_PATH = ROOT / "data" / "capabilities_modes.db"
REPORT_PATH = ROOT / "data" / "iterative_modes_report.json"

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
        "expected_repos": {"OCRmyPDF", "pytesseract"},
    },
    {
        "name": "api_service",
        "query": "python api service",
        "expected_repos": {"flask"},
    },
    {
        "name": "cli_tooling",
        "query": "python cli command tooling",
        "expected_repos": {"click", "flask", "OCRmyPDF"},
    },
]

MODES = ["lexical", "semantic", "hybrid"]


@dataclass
class ModeResult:
    mode: str
    repo_precision_at_k: float
    expected_repo_coverage: float
    results: list[dict]


@dataclass
class QueryResult:
    name: str
    query: str
    top_k: int
    mode_results: list[ModeResult]


@dataclass
class IterationResult:
    repos_indexed: list[str]
    cards_added_for_latest_repo: int
    query_results: list[QueryResult]


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
        "evidence_preview": evidence[:3],
    }


def repo_precision(results: list[dict], expected_repos: set[str], k: int) -> float:
    if not results:
        return 0.0
    denom = min(k, len(results))
    good = sum(1 for row in results[:denom] if row["repo"] in expected_repos)
    return round(good / denom, 3)


def repo_coverage(results: list[dict], expected_repos: set[str], k: int) -> float:
    if not expected_repos:
        return 0.0
    seen = {row["repo"] for row in results[:k] if row["repo"] in expected_repos}
    return round(len(seen) / len(expected_repos), 3)


def main() -> None:
    REPOS_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    init_db(DB_PATH)

    iterations: list[IterationResult] = []
    indexed_repo_names: list[str] = []

    for repo in REPOS:
        repo_path = clone_if_missing(repo["name"], repo["url"])
        cards_added = upsert_repo_and_cards(DB_PATH, repo_path, repo["name"])
        indexed_repo_names.append(repo["name"])

        query_results: list[QueryResult] = []
        for query in QUERIES:
            mode_results: list[ModeResult] = []
            for mode in MODES:
                rows = search_cards(DB_PATH, query["query"], 5, mode=mode)
                results = [to_result_dict(row) for row in rows]
                mode_results.append(
                    ModeResult(
                        mode=mode,
                        repo_precision_at_k=repo_precision(results, query["expected_repos"], 5),
                        expected_repo_coverage=repo_coverage(results, query["expected_repos"], 5),
                        results=results,
                    )
                )

            query_results.append(
                QueryResult(
                    name=query["name"],
                    query=query["query"],
                    top_k=5,
                    mode_results=mode_results,
                )
            )

        iterations.append(
            IterationResult(
                repos_indexed=list(indexed_repo_names),
                cards_added_for_latest_repo=cards_added,
                query_results=query_results,
            )
        )

    report = {
        "db_path": str(DB_PATH),
        "repo_count": len(indexed_repo_names),
        "repos": indexed_repo_names,
        "modes": MODES,
        "iterations": [
            {
                "repos_indexed": it.repos_indexed,
                "cards_added_for_latest_repo": it.cards_added_for_latest_repo,
                "query_results": [asdict(qr) for qr in it.query_results],
            }
            for it in iterations
        ],
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Wrote modes report: {REPORT_PATH}")
    final_iteration = iterations[-1]
    print("\n=== Final (5 repos) mode comparison ===")
    for query_result in final_iteration.query_results:
        print(f"{query_result.name} | query='{query_result.query}'")
        for mode_result in query_result.mode_results:
            print(
                f"  {mode_result.mode}: repo_precision@5={mode_result.repo_precision_at_k} "
                f"coverage={mode_result.expected_repo_coverage}"
            )
            for idx, result in enumerate(mode_result.results[:3], start=1):
                print(
                    f"    [{idx}] {result['repo']} | {result['capability']} "
                    f"| conf={result['confidence']}"
                )


if __name__ == "__main__":
    main()
