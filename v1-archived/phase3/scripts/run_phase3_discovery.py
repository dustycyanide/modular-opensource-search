#!/usr/bin/env python3
"""Run Phase 3 capability discovery over indexed OSS repos.

This script scans local repositories against candidate capability signal rules
and generates an evidence-backed discovery report for Phase 4 planning.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


TEXT_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".cs",
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".xml",
    ".html",
    ".css",
    ".sh",
    ".rst",
}

CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".cs",
    ".sh",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run phase3 capability discovery")
    parser.add_argument("--repos-file", help="Path to repos JSON")
    parser.add_argument(
        "--cohort-manifest",
        help="Optional cohort manifest JSON (preferred source for targeted discovery)",
    )
    parser.add_argument("--capabilities-file", required=True, help="Path to candidate capabilities JSON")
    parser.add_argument("--repos-root", default="repos", help="Local repo directory")
    parser.add_argument("--report", default="phase3/reports/discovery_report.json", help="Output report JSON")
    parser.add_argument("--max-repos", type=int, default=20, help="Maximum repos to inspect")
    parser.add_argument("--max-files-per-repo", type=int, default=700, help="Maximum files per repo")
    parser.add_argument("--max-file-size-bytes", type=int, default=200_000, help="Maximum file size to scan")
    parser.add_argument("--max-chars-per-file", type=int, default=12_000, help="Maximum chars to read per file")
    parser.add_argument("--max-evidence-per-repo", type=int, default=8, help="Maximum evidence entries per repo")
    parser.add_argument("--clone-missing", action="store_true", help="Clone repositories missing under repos-root")
    parser.add_argument(
        "--allow-weak-cohort",
        action="store_true",
        help="Proceed even if cohort manifest validation gates failed",
    )
    parser.add_argument(
        "--response",
        choices=["final", "verbose"],
        default="final",
        help="Response detail level (default: final)",
    )
    parser.add_argument("--verbose", action="store_true", help="Shortcut for --response verbose")

    args = parser.parse_args()
    if not args.repos_file and not args.cohort_manifest:
        parser.error("one of --repos-file or --cohort-manifest is required")
    return args


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def clone_if_missing(repo_name: str, repo_url: str, repos_root: Path, clone_missing: bool) -> tuple[Path | None, str | None]:
    repo_path = repos_root / repo_name
    if repo_path.exists():
        return repo_path, None

    if not clone_missing:
        return None, f"missing local repo at {repo_path}"

    if not repo_url:
        return None, f"cannot clone {repo_name}: missing repo url"

    run(["git", "clone", "--depth", "1", repo_url, str(repo_path)])
    return repo_path, None


def get_response_mode(args: argparse.Namespace) -> str:
    if getattr(args, "verbose", False):
        return "verbose"
    return getattr(args, "response", "final")


def normalize_selected_repos(
    repos_payload: dict[str, Any] | None,
    cohort_payload: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], str]:
    if cohort_payload:
        rows = []
        for entry in cohort_payload.get("selected_repos", []):
            if isinstance(entry, str):
                rows.append({"name": entry, "url": "", "priority": "medium"})
                continue

            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if not name:
                continue
            rows.append(
                {
                    "name": name,
                    "url": entry.get("url", ""),
                    "priority": entry.get("priority", "medium"),
                }
            )
        return rows, "cohort_manifest"

    if repos_payload:
        return list(repos_payload.get("repos", [])), "repos_file"
    return [], "none"


def iter_text_files(repo_path: Path, max_files: int):
    count = 0
    for file_path in repo_path.rglob("*"):
        if count >= max_files:
            break
        if not file_path.is_file():
            continue
        if "/.git/" in file_path.as_posix():
            continue
        if file_path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        count += 1
        yield file_path


def read_text(file_path: Path, max_file_size_bytes: int, max_chars_per_file: int) -> str:
    try:
        if file_path.stat().st_size > max_file_size_bytes:
            return ""
        return file_path.read_text(encoding="utf-8", errors="ignore")[:max_chars_per_file]
    except OSError:
        return ""


def compile_capability_rules(capability: dict[str, Any]) -> dict[str, Any]:
    required_groups = []
    for group in capability.get("required_groups", []):
        required_groups.append([re.compile(pattern, re.IGNORECASE) for pattern in group])

    support_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in capability.get("support_patterns", [])]

    return {
        "required_groups": required_groups,
        "support_patterns": support_patterns,
        "min_support": int(capability.get("min_support", 0)),
    }


def _quality_label(
    required_passed: bool,
    support_hits: int,
    min_support: int,
    required_groups_hit: int,
    code_evidence_hits: int,
) -> str:
    if required_passed and support_hits >= min_support and code_evidence_hits >= 2:
        return "high"
    if required_passed and support_hits >= min_support:
        return "medium"
    if required_groups_hit > 0 and support_hits > 0:
        return "low"
    return "none"


def _quality_score(
    required_groups_hit: int,
    required_group_count: int,
    support_hits: int,
    support_pattern_count: int,
    code_evidence_hits: int,
) -> float:
    if required_group_count <= 0:
        required_ratio = 0.0
    else:
        required_ratio = required_groups_hit / required_group_count

    support_denominator = max(support_pattern_count, 1)
    support_ratio = min(support_hits / support_denominator, 1.0)
    code_ratio = min(code_evidence_hits / 3.0, 1.0)
    return round((required_ratio * 0.6) + (support_ratio * 0.3) + (code_ratio * 0.1), 3)


def score_repo_capability(
    repo_path: Path,
    capability: dict[str, Any],
    compiled_rules: dict[str, Any],
    max_files_per_repo: int,
    max_file_size_bytes: int,
    max_chars_per_file: int,
    max_evidence_per_repo: int,
) -> dict[str, Any]:
    required_groups: list[list[re.Pattern]] = compiled_rules["required_groups"]
    support_patterns: list[re.Pattern] = compiled_rules["support_patterns"]
    min_support: int = compiled_rules["min_support"]

    required_group_hits = [0 for _ in required_groups]
    matched_support_patterns: set[str] = set()
    evidence: list[dict[str, str]] = []
    evidence_keys: set[tuple[str, str, str]] = set()
    code_evidence_hits = 0

    for file_path in iter_text_files(repo_path, max_files=max_files_per_repo):
        text = read_text(file_path, max_file_size_bytes=max_file_size_bytes, max_chars_per_file=max_chars_per_file)
        if not text:
            continue

        rel = file_path.relative_to(repo_path).as_posix()
        is_code_file = file_path.suffix.lower() in CODE_EXTENSIONS

        for idx, group in enumerate(required_groups):
            if required_group_hits[idx] > 0:
                continue
            for pattern in group:
                if pattern.search(text):
                    required_group_hits[idx] += 1
                    if is_code_file:
                        code_evidence_hits += 1
                    if len(evidence) < max_evidence_per_repo:
                        key = (rel, pattern.pattern, f"required_group_{idx + 1}")
                        if key not in evidence_keys:
                            evidence.append({"path": rel, "signal": pattern.pattern, "kind": f"required_group_{idx + 1}"})
                            evidence_keys.add(key)
                    break

        for pattern in support_patterns:
            if pattern.search(text):
                matched_support_patterns.add(pattern.pattern)
                if is_code_file:
                    code_evidence_hits += 1
                if len(evidence) < max_evidence_per_repo:
                    key = (rel, pattern.pattern, "support")
                    if key not in evidence_keys:
                        evidence.append({"path": rel, "signal": pattern.pattern, "kind": "support"})
                        evidence_keys.add(key)

    required_group_count = len(required_groups)
    required_groups_hit = sum(1 for value in required_group_hits if value > 0)
    required_passed = required_groups_hit == required_group_count and required_group_count > 0
    support_hits = len(matched_support_patterns)

    quality = _quality_label(
        required_passed=required_passed,
        support_hits=support_hits,
        min_support=min_support,
        required_groups_hit=required_groups_hit,
        code_evidence_hits=code_evidence_hits,
    )
    score = _quality_score(
        required_groups_hit=required_groups_hit,
        required_group_count=required_group_count,
        support_hits=support_hits,
        support_pattern_count=len(support_patterns),
        code_evidence_hits=code_evidence_hits,
    )

    return {
        "capability": capability["name"],
        "required_group_count": required_group_count,
        "required_groups_hit": required_groups_hit,
        "required_groups_passed": required_passed,
        "support_hits": support_hits,
        "support_pattern_count": len(support_patterns),
        "min_support": min_support,
        "code_evidence_hits": code_evidence_hits,
        "quality": quality,
        "quality_score": score,
        "evidence": evidence,
    }


def quality_rank(label: str) -> int:
    order = {"high": 3, "medium": 2, "low": 1, "none": 0}
    return order.get(label, 0)


def main() -> None:
    args = parse_args()
    response_mode = get_response_mode(args)

    repos_file = Path(args.repos_file).resolve() if args.repos_file else None
    cohort_manifest_path = Path(args.cohort_manifest).resolve() if args.cohort_manifest else None
    capabilities_file = Path(args.capabilities_file).resolve()
    repos_root = (ROOT / args.repos_root).resolve()
    report_path = (ROOT / args.report).resolve()

    repos_root.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    repos_payload = load_json(repos_file) if repos_file else None
    cohort_payload = load_json(cohort_manifest_path) if cohort_manifest_path else None
    capabilities_payload = load_json(capabilities_file)

    if cohort_payload and not bool(cohort_payload.get("gate_passed", False)) and not args.allow_weak_cohort:
        raise SystemExit(
            "Cohort manifest gate failed. Rebuild cohort or pass --allow-weak-cohort to proceed."
        )

    selected_repos_all, selected_repo_source = normalize_selected_repos(repos_payload, cohort_payload)
    selected_repos = selected_repos_all[: max(args.max_repos, 0)]
    if not selected_repos:
        raise SystemExit("No repositories selected for discovery.")

    if selected_repo_source == "cohort_manifest" and not args.clone_missing and not args.allow_weak_cohort:
        missing_local = [repo["name"] for repo in selected_repos if not (repos_root / repo["name"]).exists()]
        if missing_local:
            raise SystemExit(
                "Cohort manifest contains repos missing locally: "
                f"{', '.join(sorted(missing_local))}. "
                "Clone them, pass --clone-missing, or use --allow-weak-cohort."
            )

    capabilities = capabilities_payload.get("capabilities", [])

    compiled_capabilities = {
        capability["name"]: compile_capability_rules(capability)
        for capability in capabilities
    }

    repos_indexed: list[str] = []
    repos_skipped: list[dict[str, str]] = []
    repo_scan_results: dict[str, dict[str, Any]] = {}

    for repo in selected_repos:
        repo_name = repo["name"]
        repo_url = repo.get("url", "")
        repo_path, skip_reason = clone_if_missing(repo_name, repo_url, repos_root, args.clone_missing)

        if repo_path is None:
            repos_skipped.append({"repo": repo_name, "reason": skip_reason or "unknown"})
            continue

        repos_indexed.append(repo_name)
        repo_scan_results[repo_name] = {}

        for capability in capabilities:
            compiled_rules = compiled_capabilities[capability["name"]]
            scored = score_repo_capability(
                repo_path=repo_path,
                capability=capability,
                compiled_rules=compiled_rules,
                max_files_per_repo=args.max_files_per_repo,
                max_file_size_bytes=args.max_file_size_bytes,
                max_chars_per_file=args.max_chars_per_file,
                max_evidence_per_repo=args.max_evidence_per_repo,
            )
            repo_scan_results[repo_name][capability["name"]] = scored

    capability_reports = []

    for capability in capabilities:
        name = capability["name"]
        rows = []
        for repo_name in repos_indexed:
            result = repo_scan_results[repo_name][name]
            if result["quality"] == "none":
                continue
            rows.append(
                {
                    "repo": repo_name,
                    "quality": result["quality"],
                    "quality_score": result["quality_score"],
                    "required_groups_passed": result["required_groups_passed"],
                    "required_groups_hit": result["required_groups_hit"],
                    "required_group_count": result["required_group_count"],
                    "support_hits": result["support_hits"],
                    "support_pattern_count": result["support_pattern_count"],
                    "min_support": result["min_support"],
                    "code_evidence_hits": result["code_evidence_hits"],
                    "evidence": result["evidence"],
                }
            )

        rows.sort(key=lambda row: (quality_rank(row["quality"]), row["quality_score"], row["support_hits"]), reverse=True)

        summary = {
            "high_count": sum(1 for row in rows if row["quality"] == "high"),
            "medium_count": sum(1 for row in rows if row["quality"] == "medium"),
            "low_count": sum(1 for row in rows if row["quality"] == "low"),
            "matched_repo_count": len(rows),
        }

        capability_reports.append(
            {
                "name": capability["name"],
                "title": capability.get("title", capability["name"]),
                "description": capability.get("description", ""),
                "query_hints": capability.get("query_hints", []),
                "repo_types_sought": capability.get("repo_types_sought", []),
                "why_useful_here": capability.get("why_useful_here", ""),
                "signals": {
                    "required_groups": capability.get("required_groups", []),
                    "support_patterns": capability.get("support_patterns", []),
                    "min_support": int(capability.get("min_support", 0)),
                },
                "summary": summary,
                "matches": rows,
            }
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "repos_file": str(repos_file) if repos_file else None,
            "cohort_manifest": str(cohort_manifest_path) if cohort_manifest_path else None,
            "selected_repo_source": selected_repo_source,
            "cohort_gate_passed": cohort_payload.get("gate_passed") if cohort_payload else None,
            "capabilities_file": str(capabilities_file),
            "repos_root": str(repos_root),
            "max_repos": args.max_repos,
            "max_files_per_repo": args.max_files_per_repo,
            "max_file_size_bytes": args.max_file_size_bytes,
            "max_chars_per_file": args.max_chars_per_file,
            "max_evidence_per_repo": args.max_evidence_per_repo,
            "clone_missing": bool(args.clone_missing),
            "response_mode": response_mode,
        },
        "repos_indexed": repos_indexed,
        "repos_skipped": repos_skipped,
        "capability_reports": capability_reports,
    }

    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Wrote phase3 discovery report: {report_path}")
    if response_mode == "verbose":
        print(f"Selected repo source: {selected_repo_source}")
        print(f"Repos indexed={len(repos_indexed)} skipped={len(repos_skipped)}")
        for skipped in repos_skipped:
            print(f"  skipped repo={skipped.get('repo')} reason={skipped.get('reason')}")

    for capability in capability_reports:
        summary = capability["summary"]
        print(
            f"{capability['name']}: "
            f"high={summary['high_count']} "
            f"medium={summary['medium_count']} "
            f"low={summary['low_count']}"
        )


if __name__ == "__main__":
    main()
