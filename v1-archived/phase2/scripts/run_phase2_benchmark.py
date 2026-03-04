#!/usr/bin/env python3
"""Run the Phase 2 benchmark loop.

This script clones repositories (if missing), ingests them into the capability
index, executes benchmark queries across retrieval modes, and writes a report
with quality metrics plus error taxonomy counts.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

import sys

sys.path.insert(0, str(ROOT))

from capability_index import init_db, search_cards, upsert_repo_and_cards  # noqa: E402


DEFAULT_MODES = ["lexical", "semantic", "hybrid"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run phase2 benchmark")
    parser.add_argument("--repos-file", required=True, help="Path to repos JSON")
    parser.add_argument("--queries-file", required=True, help="Path to queries JSON")
    parser.add_argument("--repos-root", default="repos", help="Local directory for cloned repos")
    parser.add_argument("--db", default="data/capabilities_phase2.db", help="SQLite DB path")
    parser.add_argument("--report", default="phase2/reports/latest_report.json", help="Output report path")
    parser.add_argument("--validator-pack", default=None, help="Optional validator pack JSON path")
    parser.add_argument("--max-repos", type=int, default=5, help="Maximum repos to ingest")
    parser.add_argument("--modes", nargs="+", default=DEFAULT_MODES, choices=DEFAULT_MODES, help="Retrieval modes")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def clone_if_missing(repo_name: str, repo_url: str, repos_root: Path) -> Path:
    repo_path = repos_root / repo_name
    if repo_path.exists():
        return repo_path
    run(["git", "clone", "--depth", "1", repo_url, str(repo_path)])
    return repo_path


def to_result(row) -> dict[str, Any]:
    evidence = json.loads(row["evidence_json"] or "[]")
    return {
        "repo": row["repo_name"],
        "card_type": row["card_type"],
        "title": row["title"],
        "capability": row["capability_name"],
        "confidence": round(float(row["confidence"]), 3),
        "license": row["license"],
        "language": row["primary_language"],
        "evidence_preview": evidence[:4],
    }


def precision_at_k(items: list[dict[str, Any]], allowed: set[str], key: str, k: int) -> float:
    if not items:
        return 0.0
    denom = min(k, len(items))
    good = sum(1 for item in items[:denom] if item[key] in allowed)
    return round(good / denom, 3)


def coverage_at_k(items: list[dict[str, Any]], expected: set[str], key: str, k: int) -> float:
    if not expected:
        return 0.0
    seen = {item[key] for item in items[:k] if item[key] in expected}
    return round(len(seen) / len(expected), 3)


def classify_errors(
    results: list[dict[str, Any]],
    expected_repos: set[str],
    expected_caps: set[str],
    top_k: int,
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    counts = {
        "extraction_fp": 0,
        "extraction_fn": 0,
        "ranking_fp": 0,
        "ranking_fn": 0,
        "filter_error": 0,
        "evidence_gap": 0,
        "unknown": 0,
    }
    errors: list[dict[str, Any]] = []

    top = results[:top_k]
    returned_repos = {row["repo"] for row in top}
    returned_caps = {row["capability"] for row in top if row["card_type"] == "capability"}

    missing_repos = sorted(expected_repos - returned_repos)
    missing_caps = sorted(expected_caps - returned_caps)
    if missing_repos:
        counts["ranking_fn"] += len(missing_repos)
        for repo in missing_repos:
            errors.append({"type": "ranking_fn", "detail": f"missing expected repo: {repo}"})
    if missing_caps:
        counts["extraction_fn"] += len(missing_caps)
        for cap in missing_caps:
            errors.append({"type": "extraction_fn", "detail": f"missing expected capability: {cap}"})

    for rank, row in enumerate(top, start=1):
        repo_ok = row["repo"] in expected_repos if expected_repos else True
        cap_ok = row["capability"] in expected_caps if expected_caps else row["card_type"] != "capability"

        if not repo_ok and not cap_ok:
            counts["ranking_fp"] += 1
            errors.append({"type": "ranking_fp", "rank": rank, "detail": f"off-target result {row['repo']}:{row['capability']}"})
        elif not repo_ok:
            counts["ranking_fp"] += 1
            errors.append({"type": "ranking_fp", "rank": rank, "detail": f"unexpected repo {row['repo']}"})
        elif not cap_ok:
            counts["extraction_fp"] += 1
            errors.append({"type": "extraction_fp", "rank": rank, "detail": f"unexpected capability {row['capability']}"})

        if row["card_type"] == "capability" and not row["evidence_preview"]:
            counts["evidence_gap"] += 1
            errors.append({"type": "evidence_gap", "rank": rank, "detail": f"no evidence for {row['title']}"})

    return counts, errors


def aggregate(query_results: list[dict[str, Any]], modes: list[str]) -> dict[str, Any]:
    by_mode: dict[str, dict[str, Any]] = {}
    by_mode_family: dict[str, dict[str, dict[str, Any]]] = {}

    for mode in modes:
        mode_rows = []
        mode_family_rows: dict[str, list[dict[str, Any]]] = {}
        for query in query_results:
            payload = query["mode_results"][mode]
            row = {
                "repo_precision": payload["repo_precision_at_k"],
                "repo_coverage": payload["repo_coverage_at_k"],
                "capability_precision": payload["capability_precision_at_k"],
                "errors_total": sum(payload["error_counts"].values()),
            }
            mode_rows.append(row)
            mode_family_rows.setdefault(query["family"], []).append(row)

        by_mode[mode] = {
            "avg_repo_precision": round(statistics.mean(r["repo_precision"] for r in mode_rows), 3) if mode_rows else 0.0,
            "avg_repo_coverage": round(statistics.mean(r["repo_coverage"] for r in mode_rows), 3) if mode_rows else 0.0,
            "avg_capability_precision": round(statistics.mean(r["capability_precision"] for r in mode_rows), 3)
            if mode_rows
            else 0.0,
            "avg_errors_total": round(statistics.mean(r["errors_total"] for r in mode_rows), 3) if mode_rows else 0.0,
        }

        by_mode_family[mode] = {}
        for family, family_rows in mode_family_rows.items():
            by_mode_family[mode][family] = {
                "avg_repo_precision": round(statistics.mean(r["repo_precision"] for r in family_rows), 3),
                "avg_repo_coverage": round(statistics.mean(r["repo_coverage"] for r in family_rows), 3),
                "avg_capability_precision": round(statistics.mean(r["capability_precision"] for r in family_rows), 3),
                "avg_errors_total": round(statistics.mean(r["errors_total"] for r in family_rows), 3),
            }

    return {"by_mode": by_mode, "by_mode_family": by_mode_family}


def main() -> None:
    args = parse_args()
    repos_file = Path(args.repos_file).resolve()
    queries_file = Path(args.queries_file).resolve()
    repos_root = (ROOT / args.repos_root).resolve()
    db_path = (ROOT / args.db).resolve()
    report_path = (ROOT / args.report).resolve()
    validator_pack_path = Path(args.validator_pack).resolve() if args.validator_pack else None

    repos_root.mkdir(parents=True, exist_ok=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    repos_payload = load_json(repos_file)
    queries_payload = load_json(queries_file)

    selected_repos = repos_payload["repos"][: max(args.max_repos, 0)]

    if db_path.exists():
        db_path.unlink()
    init_db(db_path)

    ingest_summary = []
    indexed_repo_names = []

    for repo in selected_repos:
        repo_path = clone_if_missing(repo["name"], repo["url"], repos_root)
        cards_added = upsert_repo_and_cards(
            db_path=db_path,
            repo_path=repo_path,
            repo_name=repo["name"],
            validator_pack_path=validator_pack_path,
        )
        indexed_repo_names.append(repo["name"])
        ingest_summary.append({"repo": repo["name"], "cards_added": cards_added, "path": str(repo_path)})

    query_results = []
    for query_def in queries_payload["queries"]:
        query_id = query_def["id"]
        query_text = query_def["query"]
        family = query_def["family"]
        top_k = int(query_def.get("top_k", 5))
        expected_repos = set(query_def.get("expected_repos", []))
        expected_caps = set(query_def.get("expected_capabilities", []))

        mode_results: dict[str, Any] = {}
        for mode in args.modes:
            rows = search_cards(db_path, query_text, top_k, mode=mode)
            results = [to_result(row) for row in rows]

            cap_precision = (
                precision_at_k(results, expected_caps, "capability", top_k) if expected_caps else 1.0
            )
            repo_precision = precision_at_k(results, expected_repos, "repo", top_k) if expected_repos else 0.0
            repo_coverage = coverage_at_k(results, expected_repos, "repo", top_k)

            error_counts, errors = classify_errors(results, expected_repos, expected_caps, top_k)

            mode_results[mode] = {
                "repo_precision_at_k": repo_precision,
                "repo_coverage_at_k": repo_coverage,
                "capability_precision_at_k": cap_precision,
                "error_counts": error_counts,
                "errors": errors[:12],
                "results": results,
            }

        query_results.append(
            {
                "id": query_id,
                "family": family,
                "query": query_text,
                "top_k": top_k,
                "expected_repos": sorted(expected_repos),
                "expected_capabilities": sorted(expected_caps),
                "mode_results": mode_results,
            }
        )

    aggregates = aggregate(query_results, args.modes)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "repos_file": str(repos_file),
            "queries_file": str(queries_file),
            "repos_root": str(repos_root),
            "db_path": str(db_path),
            "validator_pack": str(validator_pack_path) if validator_pack_path else None,
            "max_repos": args.max_repos,
            "modes": args.modes,
        },
        "repos_indexed": indexed_repo_names,
        "ingest_summary": ingest_summary,
        "query_results": query_results,
        "aggregates": aggregates,
    }

    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Wrote phase2 report: {report_path}")
    for mode, summary in aggregates["by_mode"].items():
        print(
            f"{mode}: repo_precision={summary['avg_repo_precision']} "
            f"repo_coverage={summary['avg_repo_coverage']} "
            f"cap_precision={summary['avg_capability_precision']} "
            f"errors={summary['avg_errors_total']}"
        )


if __name__ == "__main__":
    main()
