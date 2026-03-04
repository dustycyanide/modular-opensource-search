#!/usr/bin/env python3
"""Build a capability-targeted Phase 3 cohort manifest.

This stage selects positive and contrast repositories per capability target,
applies quality and diversity constraints, and emits a reusable cohort manifest
for discovery.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


PRIORITY_SCORE = {
    "high": 0.30,
    "medium": 0.20,
    "low": 0.10,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build targeted cohort manifest for phase3 discovery")
    parser.add_argument(
        "--targeting-spec",
        default="phase3/config/capability_targeting.json",
        help="Capability targeting spec JSON",
    )
    parser.add_argument(
        "--repo-registry",
        default="phase3/config/repo_registry.json",
        help="Repository registry JSON",
    )
    parser.add_argument(
        "--output",
        default="phase3/reports/cohort_manifest.json",
        help="Output cohort manifest JSON",
    )
    parser.add_argument(
        "--max-per-ecosystem",
        type=int,
        default=2,
        help="Max selected repos per ecosystem before fallback fill",
    )
    parser.add_argument(
        "--allow-weak-cohort",
        action="store_true",
        help="Write manifest and continue even if validation gates fail",
    )
    parser.add_argument(
        "--response",
        choices=["final", "verbose"],
        default="final",
        help="Response detail level (default: final)",
    )
    parser.add_argument("--verbose", action="store_true", help="Shortcut for --response verbose")
    return parser.parse_args()


def get_response_mode(args: argparse.Namespace) -> str:
    if getattr(args, "verbose", False):
        return "verbose"
    return getattr(args, "response", "final")


def resolve_path(path_arg: str) -> Path:
    path = Path(path_arg)
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def quality_passes(repo: dict[str, Any], quality_bar: dict[str, Any]) -> tuple[bool, list[str]]:
    quality = repo.get("quality", {})
    reasons: list[str] = []

    allowed_maintained = set(quality_bar.get("maintained", []))
    maintained = quality.get("maintained", "unknown")
    if allowed_maintained and maintained not in allowed_maintained:
        reasons.append(f"maintained={maintained} not in {sorted(allowed_maintained)}")

    if bool(quality_bar.get("require_tests", False)) and not bool(quality.get("has_tests", False)):
        reasons.append("tests_required")

    if bool(quality_bar.get("require_docs", False)) and not bool(quality.get("has_docs", False)):
        reasons.append("docs_required")

    allowed_license_classes = set(quality_bar.get("allowed_license_classes", []))
    license_class = repo.get("license_class", "unknown")
    if allowed_license_classes and license_class not in allowed_license_classes:
        reasons.append(f"license_class={license_class} not in {sorted(allowed_license_classes)}")

    return (len(reasons) == 0), reasons


def capability_tokens(capability_name: str) -> set[str]:
    return {token for token in capability_name.lower().split("_") if token}


def score_positive(repo: dict[str, Any], capability_name: str, target: dict[str, Any]) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    known_caps = set(repo.get("known_capabilities", []))
    repo_type = repo.get("repo_type", "")
    tags = set(repo.get("tags", []))

    if capability_name in known_caps:
        score += 3.0
        reasons.append("known_capability_match")

    if repo_type in set(target.get("repo_types_sought", [])):
        score += 2.0
        reasons.append("repo_type_match")

    token_overlap = capability_tokens(capability_name).intersection({token.lower() for token in tags})
    if token_overlap:
        score += 1.0
        reasons.append("tag_overlap")

    quality = repo.get("quality", {})
    if bool(quality.get("has_tests", False)):
        score += 0.2
    if bool(quality.get("has_docs", False)):
        score += 0.2

    score += PRIORITY_SCORE.get(str(repo.get("priority", "medium")).lower(), 0.0)
    return round(score, 3), reasons


def score_contrast(repo: dict[str, Any], capability_name: str, target: dict[str, Any]) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    known_caps = set(repo.get("known_capabilities", []))
    repo_type = repo.get("repo_type", "")
    contrast_for = set(repo.get("contrast_for", []))

    if repo_type in set(target.get("contrast_repo_types", [])):
        score += 2.0
        reasons.append("contrast_repo_type")

    if "negative_control" in known_caps:
        score += 3.0
        reasons.append("negative_control")

    if capability_name in contrast_for:
        score += 2.0
        reasons.append("explicit_contrast_for_capability")

    score += PRIORITY_SCORE.get(str(repo.get("priority", "medium")).lower(), 0.0)
    return round(score, 3), reasons


def select_diverse(
    rows: list[dict[str, Any]],
    target_count: int,
    max_per_ecosystem: int,
) -> list[dict[str, Any]]:
    if target_count <= 0:
        return []

    selected: list[dict[str, Any]] = []
    selected_names: set[str] = set()
    ecosystem_counts: Counter = Counter()

    for row in rows:
        if len(selected) >= target_count:
            break
        ecosystem = row.get("ecosystem", "unknown")
        name = row.get("name")
        if not name or name in selected_names:
            continue
        if ecosystem_counts[ecosystem] >= max_per_ecosystem:
            continue
        selected.append(row)
        selected_names.add(name)
        ecosystem_counts[ecosystem] += 1

    if len(selected) >= target_count:
        return selected

    for row in rows:
        if len(selected) >= target_count:
            break
        name = row.get("name")
        if not name or name in selected_names:
            continue
        selected.append(row)
        selected_names.add(name)

    return selected


def row_view(repo: dict[str, Any], score: float, reasons: list[str]) -> dict[str, Any]:
    return {
        "name": repo["name"],
        "url": repo.get("url", ""),
        "repo_type": repo.get("repo_type", "Unknown"),
        "ecosystem": repo.get("ecosystem", "unknown"),
        "priority": repo.get("priority", "medium"),
        "quality": repo.get("quality", {}),
        "known_capabilities": repo.get("known_capabilities", []),
        "score": score,
        "selection_reasons": reasons,
    }


def validate_cohort(target: dict[str, Any], positive: list[dict[str, Any]], contrast: list[dict[str, Any]]) -> dict[str, Any]:
    min_positive = int(target.get("min_positive_repos", 0))
    min_contrast = int(target.get("min_contrast_repos", 0))
    min_distinct_ecosystems = int(target.get("min_distinct_ecosystems", 1))

    positive_count = len(positive)
    contrast_count = len(contrast)
    distinct_ecosystems = len({row.get("ecosystem", "unknown") for row in positive})

    checks = {
        "positive_quota": positive_count >= min_positive,
        "contrast_quota": contrast_count >= min_contrast,
        "ecosystem_diversity": distinct_ecosystems >= min_distinct_ecosystems,
    }

    failures = []
    if not checks["positive_quota"]:
        failures.append(f"positive_quota failed: have={positive_count} need={min_positive}")
    if not checks["contrast_quota"]:
        failures.append(f"contrast_quota failed: have={contrast_count} need={min_contrast}")
    if not checks["ecosystem_diversity"]:
        failures.append(f"ecosystem_diversity failed: have={distinct_ecosystems} need={min_distinct_ecosystems}")

    return {
        "checks": checks,
        "passed": all(checks.values()),
        "failures": failures,
        "positive_count": positive_count,
        "contrast_count": contrast_count,
        "distinct_positive_ecosystems": distinct_ecosystems,
    }


def main() -> None:
    args = parse_args()
    response_mode = get_response_mode(args)

    targeting_path = resolve_path(args.targeting_spec)
    registry_path = resolve_path(args.repo_registry)
    output_path = resolve_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    targeting = load_json(targeting_path)
    registry = load_json(registry_path)

    capabilities = targeting.get("capabilities", [])
    repos = registry.get("repos", [])

    capability_cohorts: list[dict[str, Any]] = []
    selected_repo_index: dict[str, dict[str, Any]] = {}
    selected_repo_links: dict[str, list[dict[str, str]]] = defaultdict(list)
    gate_failures: list[dict[str, Any]] = []

    for target in capabilities:
        capability_name = target["name"]
        quality_bar = target.get("quality_bar", {})

        positive_candidates: list[dict[str, Any]] = []
        contrast_candidates: list[dict[str, Any]] = []

        for repo in repos:
            quality_ok, _quality_reasons = quality_passes(repo, quality_bar)
            if not quality_ok:
                continue

            pos_score, pos_reasons = score_positive(repo, capability_name, target)
            if pos_score > 0 and pos_reasons:
                positive_candidates.append(row_view(repo, pos_score, pos_reasons))

            contrast_score, contrast_reasons = score_contrast(repo, capability_name, target)
            if contrast_score > 0 and contrast_reasons:
                contrast_candidates.append(row_view(repo, contrast_score, contrast_reasons))

        positive_candidates.sort(key=lambda row: row.get("score", 0.0), reverse=True)
        contrast_candidates.sort(key=lambda row: row.get("score", 0.0), reverse=True)

        selected_positive = select_diverse(
            positive_candidates,
            target_count=int(target.get("min_positive_repos", 0)),
            max_per_ecosystem=max(args.max_per_ecosystem, 1),
        )

        positive_names = {row["name"] for row in selected_positive}
        filtered_contrast_candidates = [row for row in contrast_candidates if row["name"] not in positive_names]
        selected_contrast = select_diverse(
            filtered_contrast_candidates,
            target_count=int(target.get("min_contrast_repos", 0)),
            max_per_ecosystem=max(args.max_per_ecosystem, 1),
        )

        validation = validate_cohort(target, selected_positive, selected_contrast)
        if not validation["passed"]:
            gate_failures.append({"capability": capability_name, "failures": validation["failures"]})

        capability_cohorts.append(
            {
                "capability": capability_name,
                "meaning": target.get("meaning", ""),
                "repo_types_sought": target.get("repo_types_sought", []),
                "contrast_repo_types": target.get("contrast_repo_types", []),
                "requirements": {
                    "min_positive_repos": int(target.get("min_positive_repos", 0)),
                    "min_contrast_repos": int(target.get("min_contrast_repos", 0)),
                    "min_distinct_ecosystems": int(target.get("min_distinct_ecosystems", 1)),
                    "quality_bar": quality_bar,
                },
                "selected_positive": selected_positive,
                "selected_contrast": selected_contrast,
                "validation": validation,
            }
        )

        for role, rows in (("positive", selected_positive), ("contrast", selected_contrast)):
            for row in rows:
                name = row["name"]
                selected_repo_links[name].append({"capability": capability_name, "role": role})
                selected_repo_index[name] = {
                    "name": row["name"],
                    "url": row.get("url", ""),
                    "repo_type": row.get("repo_type", "Unknown"),
                    "ecosystem": row.get("ecosystem", "unknown"),
                    "priority": row.get("priority", "medium"),
                }

    selected_repos = []
    for name in sorted(selected_repo_index.keys()):
        selected_repos.append(
            {
                **selected_repo_index[name],
                "included_for": selected_repo_links[name],
            }
        )

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "targeting_spec": str(targeting_path),
            "repo_registry": str(registry_path),
            "max_per_ecosystem": args.max_per_ecosystem,
            "response_mode": response_mode,
        },
        "capability_cohorts": capability_cohorts,
        "selected_repos": selected_repos,
        "gate_passed": len(gate_failures) == 0,
        "gate_failures": gate_failures,
    }

    output_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Wrote cohort manifest: {output_path}")
    for row in capability_cohorts:
        validation = row["validation"]
        print(
            f"{row['capability']}: "
            f"positive={validation['positive_count']} "
            f"contrast={validation['contrast_count']} "
            f"ecosystems={validation['distinct_positive_ecosystems']} "
            f"gate={'pass' if validation['passed'] else 'fail'}"
        )

    if response_mode == "verbose":
        print(f"Selected repos={len(selected_repos)}")
        for repo in selected_repos:
            links = ", ".join(f"{item['capability']}:{item['role']}" for item in repo.get("included_for", []))
            print(f"  repo={repo['name']} ecosystem={repo['ecosystem']} included_for={links}")

    if not manifest["gate_passed"] and not args.allow_weak_cohort:
        raise SystemExit("Cohort validation gates failed. Review gate_failures in cohort manifest.")


if __name__ == "__main__":
    main()
