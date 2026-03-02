#!/usr/bin/env python3
"""Generate Phase 4 integration planning artifacts from Phase 3 discovery."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


STOPWORDS = {
    "and",
    "for",
    "with",
    "from",
    "the",
    "this",
    "that",
    "into",
    "over",
    "under",
    "through",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run phase4 integration planning")
    parser.add_argument("--discovery-report", required=True, help="Phase3 discovery report JSON")
    parser.add_argument(
        "--stability-report",
        default=None,
        help="Optional second discovery report used to check decision stability",
    )
    parser.add_argument(
        "--cohort-manifest",
        default=None,
        help="Optional cohort manifest JSON to enrich memo context",
    )
    parser.add_argument("--output-dir", default="phase4/integration", help="Output directory")
    parser.add_argument(
        "--repo-profiles",
        default="phase2/benchmark/repo_profiles.json",
        help="Optional repo profile metadata JSON",
    )
    parser.add_argument("--min-quality-score", type=float, default=0.55, help="Minimum score for counting high/medium matches")
    parser.add_argument("--min-high-matches", type=int, default=2, help="High-quality matches required for adopt")
    parser.add_argument("--min-total-matches", type=int, default=3, help="High+medium matches required for adapt")
    parser.add_argument(
        "--max-high-ratio-for-adopt",
        type=float,
        default=0.45,
        help="Maximum high-match ratio for adopt (higher implies broad/noisy signals)",
    )
    parser.add_argument("--max-expected-repos", type=int, default=3, help="Maximum expected repos per generated query")
    parser.add_argument("--max-listed-matches", type=int, default=6, help="Max repos listed per capability in memo")
    parser.add_argument(
        "--response",
        choices=["final", "verbose"],
        default="final",
        help="Response detail level (default: final)",
    )
    parser.add_argument("--verbose", action="store_true", help="Shortcut for --response verbose")
    return parser.parse_args()


def resolve_path(path_arg: str) -> Path:
    path = Path(path_arg)
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def get_response_mode(args: argparse.Namespace) -> str:
    if getattr(args, "verbose", False):
        return "verbose"
    return getattr(args, "response", "final")


def normalize_slug(name: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "-", name.upper()).strip("-")


def extract_keywords(query_hints: list[str], limit: int = 8) -> list[str]:
    tokens: list[str] = []
    for query in query_hints:
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", query.lower()):
            if token in STOPWORDS:
                continue
            if token not in tokens:
                tokens.append(token)
            if len(tokens) >= limit:
                return tokens
    return tokens


def default_pipeline_for(name: str) -> str:
    mapping = {
        "repo_indexing_pipeline": "clone -> scan -> extract metadata -> index persist",
        "semantic_retrieval_stack": "embed -> index vectors -> retrieve -> rank",
        "evaluation_harness": "run benchmark -> score metrics -> compare deltas",
        "structured_filtering": "parse filters -> normalize metadata -> constrain ranking",
    }
    return mapping.get(name, "detect -> validate -> integrate")


def decide_capability(
    matches: list[dict[str, Any]],
    repos_indexed_count: int,
    min_quality_score: float,
    min_high_matches: int,
    min_total_matches: int,
) -> tuple[str, dict[str, int | float], str]:
    high = [row for row in matches if row.get("quality") == "high" and float(row.get("quality_score", 0)) >= min_quality_score]
    medium = [row for row in matches if row.get("quality") == "medium" and float(row.get("quality_score", 0)) >= min_quality_score]

    high_ratio = (len(high) / repos_indexed_count) if repos_indexed_count > 0 else 0.0

    if len(high) >= min_high_matches:
        return "adopt", {"high": len(high), "medium": len(medium), "high_ratio": round(high_ratio, 3)}, "high-signal"

    if len(high) + len(medium) >= min_total_matches and len(high) >= 1:
        return "adapt", {"high": len(high), "medium": len(medium), "high_ratio": round(high_ratio, 3)}, "medium-signal"

    return "reject", {"high": len(high), "medium": len(medium), "high_ratio": round(high_ratio, 3)}, "weak-signal"


def build_decisions_for_report(
    *,
    capability_reports: list[dict[str, Any]],
    repos_indexed_count: int,
    min_quality_score: float,
    min_high_matches: int,
    min_total_matches: int,
    max_high_ratio_for_adopt: float,
    max_expected_repos: int,
) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []

    for capability in capability_reports:
        name = capability["name"]
        matches = capability.get("matches", [])

        decision, counts, decision_reason = decide_capability(
            matches=matches,
            repos_indexed_count=repos_indexed_count,
            min_quality_score=min_quality_score,
            min_high_matches=min_high_matches,
            min_total_matches=min_total_matches,
        )

        if decision == "adopt" and float(counts["high_ratio"]) > max_high_ratio_for_adopt:
            decision = "adapt"
            decision_reason = "broad-signal"

        top_matches = [
            row
            for row in matches
            if row.get("quality") in {"high", "medium"} and float(row.get("quality_score", 0.0)) >= min_quality_score
        ]
        top_expected_repos = [row["repo"] for row in top_matches[: max_expected_repos]]

        decisions.append(
            {
                "capability": name,
                "decision": decision,
                "decision_reason": decision_reason,
                "high_count": counts["high"],
                "medium_count": counts["medium"],
                "high_ratio": counts["high_ratio"],
                "top_expected_repos": top_expected_repos,
            }
        )

    return decisions


def build_stability_check(
    primary_decisions: list[dict[str, Any]],
    secondary_decisions: list[dict[str, Any]] | None,
    secondary_report_path: Path | None,
) -> dict[str, Any]:
    if secondary_decisions is None:
        return {
            "status": "pending",
            "compared_report": str(secondary_report_path) if secondary_report_path else None,
            "agreement_ratio": None,
            "decision_drift": [],
            "lock_recommendations": False,
            "reason": "stability_report_missing",
        }

    secondary_by_capability = {row["capability"]: row for row in secondary_decisions}
    drifts: list[dict[str, Any]] = []
    comparable = 0
    matches = 0

    for row in primary_decisions:
        capability = row["capability"]
        other = secondary_by_capability.get(capability)
        if not other:
            continue
        comparable += 1
        if row["decision"] == other["decision"]:
            matches += 1
            continue
        drifts.append(
            {
                "capability": capability,
                "primary_decision": row["decision"],
                "secondary_decision": other["decision"],
            }
        )

    agreement_ratio = round(matches / comparable, 3) if comparable else 0.0
    stable = comparable > 0 and len(drifts) == 0
    return {
        "status": "stable" if stable else "unstable",
        "compared_report": str(secondary_report_path) if secondary_report_path else None,
        "agreement_ratio": agreement_ratio,
        "decision_drift": drifts,
        "lock_recommendations": stable,
        "reason": "stable_across_reports" if stable else "decision_drift_detected",
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_repo_profiles(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = load(path)
    index: dict[str, dict[str, Any]] = {}
    for row in payload.get("repos", []):
        name = row.get("name")
        if not name:
            continue
        index[name] = row
    return index


def option_tradeoffs(capability_name: str, high_ratio: float, decision_reason: str) -> list[dict[str, Any]]:
    broad_signal_risk = "medium" if high_ratio > 0.45 or decision_reason == "broad-signal" else "low"
    return [
        {
            "option": "adopt",
            "label": "Adopt now",
            "pros": [
                "Fastest path to shipping measurable value",
                "Keeps momentum when evidence is already strong",
            ],
            "cons": [
                f"Risk of overfitting if signal breadth is {broad_signal_risk}",
                "May pull in patterns that are not specific to our domain",
            ],
            "best_when": f"The capability has specific, high-quality matches and clear fit for `{capability_name}`",
        },
        {
            "option": "adapt",
            "label": "Adapt first",
            "pros": [
                "Balances speed and safety by tailoring to project constraints",
                "Reduces false positives before capability promotion",
            ],
            "cons": [
                "Adds design and implementation time",
                "Needs another evaluation loop before final acceptance",
            ],
            "best_when": "Signal is promising but too broad, noisy, or only partially specific",
        },
        {
            "option": "reject",
            "label": "Reject for now",
            "pros": [
                "Avoids introducing low-confidence behavior",
                "Protects trust while discovery criteria are refined",
            ],
            "cons": [
                "Delays potential capability gains",
                "Requires a new repo cohort or sharper detection patterns",
            ],
            "best_when": "Required signals do not pass consistently or evidence is mostly generic",
        },
    ]


def summarize_repo(repo: str, repo_profiles: dict[str, dict[str, Any]]) -> dict[str, Any]:
    profile = repo_profiles.get(repo, {})
    return {
        "name": repo,
        "repo_type": profile.get("repo_type", "Unknown"),
        "primary_capabilities": profile.get("primary_capabilities", []),
        "why_included": profile.get("why_included", "No profile summary available."),
    }


def recommendation_rationale(decision_row: dict[str, Any]) -> str:
    decision = decision_row["decision"]
    reason = decision_row["decision_reason"]
    high = decision_row["high_count"]
    medium = decision_row["medium_count"]
    high_ratio = decision_row["high_ratio"]

    if decision == "adopt":
        return (
            f"Recommend adopt because we have enough high-confidence matches (high={high}, medium={medium}) "
            f"and the signal is not too broad (high_ratio={high_ratio})."
        )
    if decision == "adapt":
        return (
            f"Recommend adapt because the capability is useful but needs tailoring before rollout "
            f"(reason={reason}, high={high}, medium={medium}, high_ratio={high_ratio})."
        )
    return (
        f"Recommend reject for now because confidence is weak or too generic "
        f"(reason={reason}, high={high}, medium={medium}, high_ratio={high_ratio})."
    )


def build_decision_memo_payload(
    *,
    discovery_report_path: Path,
    decisions: list[dict[str, Any]],
    capability_reports: list[dict[str, Any]],
    repos_indexed: list[str],
    repo_profiles: dict[str, dict[str, Any]],
    cohort_manifest: dict[str, Any] | None,
    stability_check: dict[str, Any],
    max_listed_matches: int,
) -> dict[str, Any]:
    capability_by_name = {row["name"]: row for row in capability_reports}

    cohort_selected = (cohort_manifest or {}).get("selected_repos", [])
    if cohort_selected:
        evaluated_repo_names = []
        for row in cohort_selected:
            if isinstance(row, dict) and row.get("name"):
                evaluated_repo_names.append(row["name"])
    else:
        evaluated_repo_names = list(repos_indexed)

    evaluated_repos = [summarize_repo(repo, repo_profiles) for repo in evaluated_repo_names]

    cohort_by_capability: dict[str, dict[str, Any]] = {}
    for row in (cohort_manifest or {}).get("capability_cohorts", []):
        capability_name = row.get("capability")
        if capability_name:
            cohort_by_capability[capability_name] = row

    repo_types_sought = []
    for row in capability_reports:
        capability_name = row.get("name")
        cohort_row = cohort_by_capability.get(capability_name, {})
        repo_types_sought.append(
            {
                "capability": capability_name,
                "repo_types_sought": row.get("repo_types_sought", []) or cohort_row.get("repo_types_sought", []),
                "contrast_repo_types": row.get("contrast_repo_types", []) or cohort_row.get("contrast_repo_types", []),
            }
        )

    observed_by_repo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for capability in capability_reports:
        cap_name = capability.get("name", "")
        for match in capability.get("matches", []):
            repo = match.get("repo")
            if not repo:
                continue
            observed_by_repo[repo].append(
                {
                    "capability": cap_name,
                    "quality": match.get("quality", "none"),
                    "quality_score": match.get("quality_score", 0.0),
                }
            )

    capabilities_observed = []
    for repo in sorted(observed_by_repo.keys()):
        entries = sorted(
            observed_by_repo[repo],
            key=lambda row: (
                {"high": 3, "medium": 2, "low": 1, "none": 0}.get(row.get("quality", "none"), 0),
                float(row.get("quality_score", 0.0)),
            ),
            reverse=True,
        )
        capabilities_observed.append({"repo": repo, "observed": entries[: max_listed_matches]})

    capability_sections: list[dict[str, Any]] = []
    for decision_row in decisions:
        name = decision_row["capability"]
        capability = capability_by_name.get(name, {})
        matches = capability.get("matches", [])

        ranked_matches = sorted(
            matches,
            key=lambda row: (
                {"high": 3, "medium": 2, "low": 1, "none": 0}.get(row.get("quality", "none"), 0),
                float(row.get("quality_score", 0.0)),
            ),
            reverse=True,
        )

        high_medium = [row for row in ranked_matches if row.get("quality") in {"high", "medium"}][:max_listed_matches]
        low = [row for row in ranked_matches if row.get("quality") == "low"][: max(2, min(4, max_listed_matches))]

        found_high_medium = []
        for row in high_medium:
            profile = summarize_repo(row["repo"], repo_profiles)
            found_high_medium.append(
                {
                    "repo": row["repo"],
                    "quality": row.get("quality", "unknown"),
                    "quality_score": row.get("quality_score", 0.0),
                    "repo_type": profile["repo_type"],
                    "repo_capabilities": profile["primary_capabilities"],
                    "why_included": profile["why_included"],
                }
            )

        found_low = []
        for row in low:
            profile = summarize_repo(row["repo"], repo_profiles)
            found_low.append(
                {
                    "repo": row["repo"],
                    "quality": row.get("quality", "unknown"),
                    "quality_score": row.get("quality_score", 0.0),
                    "repo_type": profile["repo_type"],
                }
            )

        capability_sections.append(
            {
                "capability": name,
                "title": capability.get("title", name),
                "description": capability.get("description", ""),
                "why_useful_here": capability.get("why_useful_here", ""),
                "repo_types_sought": capability.get("repo_types_sought", []),
                "query_hints": capability.get("query_hints", []),
                "summary": capability.get("summary", {}),
                "decision": decision_row["decision"],
                "decision_reason": decision_row["decision_reason"],
                "stable_across_runs": decision_row.get("stable_across_runs"),
                "recommendation_rationale": recommendation_rationale(decision_row),
                "options_considered": option_tradeoffs(name, float(decision_row["high_ratio"]), decision_row["decision_reason"]),
                "found_high_medium": found_high_medium,
                "found_low": found_low,
            }
        )

    grouped = {
        "adopt": [row["capability"] for row in decisions if row["decision"] == "adopt"],
        "adapt": [row["capability"] for row in decisions if row["decision"] == "adapt"],
        "reject": [row["capability"] for row in decisions if row["decision"] == "reject"],
    }

    options_considered = [
        {
            "capability": row["capability"],
            "options": row.get("options_considered", []),
        }
        for row in capability_sections
    ]

    final_recommendation = {
        "lock_recommendations": bool(stability_check.get("lock_recommendations", False)),
        "stability_check": stability_check,
        "recommendations": grouped,
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_discovery_report": str(discovery_report_path),
        "repo_types_sought": repo_types_sought,
        "repos_evaluated": evaluated_repos,
        "capabilities_observed": capabilities_observed,
        "options_considered": options_considered,
        "final_recommendation": final_recommendation,
        "evaluated_repos": evaluated_repos,
        "capability_evaluations": capability_sections,
        "final_recommendations": grouped,
    }


def render_decision_memo_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Capability Decision Memo")
    lines.append("")
    lines.append(f"Generated: `{payload['generated_at']}`")
    lines.append(f"Source discovery report: `{payload['source_discovery_report']}`")
    lines.append("")

    lines.append("## Repo Types Sought")
    lines.append("")
    lines.append("| Capability | Repo types sought | Contrast repo types |")
    lines.append("| --- | --- | --- |")
    for row in payload.get("repo_types_sought", []):
        sought = ", ".join(row.get("repo_types_sought", [])) or "-"
        contrast = ", ".join(row.get("contrast_repo_types", [])) or "-"
        lines.append(f"| `{row.get('capability', '-')}` | {sought} | {contrast} |")

    lines.append("")
    lines.append("## Repositories Evaluated")
    lines.append("")
    lines.append("| Repo | Type | Known capabilities | Why it was in scope |")
    lines.append("| --- | --- | --- | --- |")
    for repo in payload.get("repos_evaluated", []):
        known = ", ".join(repo.get("primary_capabilities", [])) or "-"
        lines.append(f"| `{repo['name']}` | {repo.get('repo_type', 'Unknown')} | {known} | {repo.get('why_included', '-')} |")

    lines.append("")
    lines.append("## Capabilities Observed")
    lines.append("")
    for row in payload.get("capabilities_observed", []):
        observed = row.get("observed", [])
        if observed:
            observed_summary = "; ".join(
                f"{item.get('capability')} ({item.get('quality')}, score={item.get('quality_score')})"
                for item in observed
            )
        else:
            observed_summary = "none"
        lines.append(f"- `{row.get('repo', '-')}`: {observed_summary}")

    for section in payload.get("capability_evaluations", []):
        lines.append("")
        lines.append(f"## {section['title']} (`{section['capability']}`)")
        lines.append("")
        lines.append(f"- What this capability is: {section.get('description', 'No description provided.')}")
        lines.append(f"- Why this is useful here: {section.get('why_useful_here', 'No project-specific rationale provided.')}")

        repo_types = section.get("repo_types_sought", [])
        if repo_types:
            lines.append(f"- Type of repos we looked for: {'; '.join(repo_types)}")

        summary = section.get("summary", {})
        lines.append(
            "- Discovery outcome: "
            f"high={summary.get('high_count', 0)}, "
            f"medium={summary.get('medium_count', 0)}, "
            f"low={summary.get('low_count', 0)}, "
            f"matched_repos={summary.get('matched_repo_count', 0)}"
        )

        lines.append("- Repos where we found strongest signal:")
        strongest = section.get("found_high_medium", [])
        if strongest:
            for row in strongest:
                caps = ", ".join(row.get("repo_capabilities", [])) or "unknown"
                lines.append(
                    f"  - `{row['repo']}` ({row.get('repo_type', 'Unknown')}, quality={row.get('quality')}, score={row.get('quality_score')}): "
                    f"known capabilities [{caps}]"
                )
        else:
            lines.append("  - No high/medium matches were found.")

        low_rows = section.get("found_low", [])
        if low_rows:
            low_summary = ", ".join(f"{row['repo']} ({row.get('quality')})" for row in low_rows)
            lines.append(f"- Lower-confidence matches we treated cautiously: {low_summary}")

        lines.append("- Options considered and trade-offs:")
        for option in section.get("options_considered", []):
            pros = "; ".join(option.get("pros", []))
            cons = "; ".join(option.get("cons", []))
            lines.append(f"  - {option.get('label', option.get('option'))}: pros={pros}. cons={cons}. Best when: {option.get('best_when', '')}")

        lines.append(
            f"- Final recommendation: `{section.get('decision')}` ({section.get('decision_reason')}). "
            f"{section.get('recommendation_rationale', '')}"
        )
        stability = section.get("stable_across_runs")
        if stability is True:
            lines.append("- Decision stability: stable across compared runs.")
        elif stability is False:
            lines.append("- Decision stability: unstable across compared runs.")
        else:
            lines.append("- Decision stability: pending broader rerun.")

    final_recommendation = payload.get("final_recommendation", {})
    recommendations = final_recommendation.get("recommendations", payload.get("final_recommendations", {}))
    stability_check = final_recommendation.get("stability_check", {})
    lines.append("")
    lines.append("## Final Recommendation")
    lines.append("")
    lines.append(f"- Recommendation lock: `{final_recommendation.get('lock_recommendations', False)}`")
    lines.append(f"- Stability status: `{stability_check.get('status', 'pending')}`")
    if stability_check.get("compared_report"):
        lines.append(f"- Stability compared report: `{stability_check.get('compared_report')}`")
    if stability_check.get("agreement_ratio") is not None:
        lines.append(f"- Stability agreement ratio: {stability_check.get('agreement_ratio')}")
    drifts = stability_check.get("decision_drift", [])
    if drifts:
        lines.append("- Decision drift detected:")
        for drift in drifts:
            lines.append(
                f"  - `{drift.get('capability')}`: primary={drift.get('primary_decision')} secondary={drift.get('secondary_decision')}"
            )

    lines.append(f"- Adopt: {', '.join(recommendations.get('adopt', [])) or '-'}")
    lines.append(f"- Adapt: {', '.join(recommendations.get('adapt', [])) or '-'}")
    lines.append(f"- Reject: {', '.join(recommendations.get('reject', [])) or '-'}")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    response_mode = get_response_mode(args)

    discovery_report_path = resolve_path(args.discovery_report)
    stability_report_path = resolve_path(args.stability_report) if args.stability_report else None
    cohort_manifest_path = resolve_path(args.cohort_manifest) if args.cohort_manifest else None
    output_dir = resolve_path(args.output_dir)
    repo_profiles_path = resolve_path(args.repo_profiles)
    output_dir.mkdir(parents=True, exist_ok=True)

    discovery = load(discovery_report_path)
    stability_discovery = load(stability_report_path) if stability_report_path else None
    cohort_manifest = load(cohort_manifest_path) if cohort_manifest_path and cohort_manifest_path.exists() else None

    capability_reports = discovery.get("capability_reports", [])
    repos_indexed = discovery.get("repos_indexed", [])
    repos_indexed_count = len(repos_indexed)
    repo_profiles = load_repo_profiles(repo_profiles_path)

    decisions = build_decisions_for_report(
        capability_reports=capability_reports,
        repos_indexed_count=repos_indexed_count,
        min_quality_score=args.min_quality_score,
        min_high_matches=args.min_high_matches,
        min_total_matches=args.min_total_matches,
        max_high_ratio_for_adopt=args.max_high_ratio_for_adopt,
        max_expected_repos=args.max_expected_repos,
    )

    secondary_decisions = None
    if stability_discovery is not None:
        secondary_capability_reports = stability_discovery.get("capability_reports", [])
        secondary_repos_indexed = stability_discovery.get("repos_indexed", [])
        secondary_decisions = build_decisions_for_report(
            capability_reports=secondary_capability_reports,
            repos_indexed_count=len(secondary_repos_indexed),
            min_quality_score=args.min_quality_score,
            min_high_matches=args.min_high_matches,
            min_total_matches=args.min_total_matches,
            max_high_ratio_for_adopt=args.max_high_ratio_for_adopt,
            max_expected_repos=args.max_expected_repos,
        )

    stability_check = build_stability_check(
        primary_decisions=decisions,
        secondary_decisions=secondary_decisions,
        secondary_report_path=stability_report_path,
    )

    drift_capabilities = {row["capability"] for row in stability_check.get("decision_drift", [])}
    for row in decisions:
        if stability_check.get("status") == "stable":
            row["stable_across_runs"] = True
        elif stability_check.get("status") == "unstable":
            row["stable_across_runs"] = row["capability"] not in drift_capabilities
        else:
            row["stable_across_runs"] = None

    decisions_by_capability = {row["capability"]: row for row in decisions}

    candidate_capabilities: list[dict[str, Any]] = []
    candidate_validator_pack: dict[str, Any] = {}
    candidate_queries: list[dict[str, Any]] = []

    for capability in capability_reports:
        name = capability["name"]
        title = capability.get("title", name)
        description = capability.get("description", "")
        query_hints = capability.get("query_hints", [])
        signals = capability.get("signals", {})
        decision_row = decisions_by_capability.get(name)
        if not decision_row:
            continue

        decision = decision_row["decision"]

        if decision == "reject":
            continue

        keywords = extract_keywords(query_hints)
        strong_keywords = keywords[:4]

        candidate_capabilities.append(
            {
                "name": name,
                "title": title,
                "description": description,
                "keywords": keywords,
                "strong_keywords": strong_keywords,
                "default_pipeline": default_pipeline_for(name),
                "decision": decision,
                "decision_locked": bool(stability_check.get("lock_recommendations", False)),
                "stable_across_runs": decision_row.get("stable_across_runs"),
            }
        )

        candidate_validator_pack[name] = {
            "required_groups": signals.get("required_groups", []),
            "support_patterns": signals.get("support_patterns", []),
            "min_support": int(signals.get("min_support", 0)),
        }

        query_text = query_hints[0] if query_hints else name.replace("_", " ")
        candidate_queries.append(
            {
                "id": f"Q-{normalize_slug(name)}-001",
                "family": name.split("_", 1)[0],
                "query": query_text,
                "top_k": 5,
                "expected_repos": decision_row.get("top_expected_repos", []),
                "expected_capabilities": [name],
            }
        )

    decisions_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_discovery_report": str(discovery_report_path),
        "repo_profiles": str(repo_profiles_path) if repo_profiles else None,
        "thresholds": {
            "min_quality_score": args.min_quality_score,
            "min_high_matches": args.min_high_matches,
            "min_total_matches": args.min_total_matches,
            "max_high_ratio_for_adopt": args.max_high_ratio_for_adopt,
            "max_expected_repos": args.max_expected_repos,
        },
        "stability_check": stability_check,
        "recommendation_lock": bool(stability_check.get("lock_recommendations", False)),
        "decisions": decisions,
    }

    capabilities_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_discovery_report": str(discovery_report_path),
        "capabilities": candidate_capabilities,
    }

    validator_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_discovery_report": str(discovery_report_path),
        "validator_overrides": candidate_validator_pack,
    }

    queries_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_discovery_report": str(discovery_report_path),
        "queries": candidate_queries,
    }

    write_json(output_dir / "candidate_decisions.json", decisions_payload)
    write_json(output_dir / "candidate_capabilities.json", capabilities_payload)
    write_json(output_dir / "candidate_validator_pack.json", validator_payload)
    write_json(output_dir / "candidate_queries.json", queries_payload)

    md_lines = [
        "# Phase 4 Integration Backlog",
        "",
        f"Source report: `{discovery_report_path}`",
        "",
        "| Capability | Decision | Reason | High | Medium | High ratio | Expected repos |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]

    for row in decisions:
        repos = ", ".join(row["top_expected_repos"]) if row["top_expected_repos"] else "-"
        md_lines.append(
            f"| `{row['capability']}` | `{row['decision']}` | `{row['decision_reason']}` | {row['high_count']} | {row['medium_count']} | {row['high_ratio']} | {repos} |"
        )

    md_lines.extend(
        [
            "",
            "## Next actions",
            "",
            "- Apply `candidate_capabilities.json` entries to `capability_index.py` capability schema.",
            "- Merge `candidate_validator_pack.json` entries into a new phase2 validator pack candidate.",
            "- Append `candidate_queries.json` into benchmark queries for regression checks.",
            "- Run the phase2 benchmark loop and compare against baseline before accepting changes.",
            "",
        ]
    )

    backlog_path = output_dir / "integration_backlog.md"
    backlog_path.write_text("\n".join(md_lines), encoding="utf-8")

    memo_payload = build_decision_memo_payload(
        discovery_report_path=discovery_report_path,
        decisions=decisions,
        capability_reports=capability_reports,
        repos_indexed=repos_indexed,
        repo_profiles=repo_profiles,
        cohort_manifest=cohort_manifest,
        stability_check=stability_check,
        max_listed_matches=args.max_listed_matches,
    )
    write_json(output_dir / "decision_memo.json", memo_payload)

    memo_markdown = render_decision_memo_markdown(memo_payload)
    memo_path = output_dir / "decision_memo.md"
    memo_path.write_text(memo_markdown, encoding="utf-8")

    print(f"Wrote phase4 planning artifacts to: {output_dir}")
    print(
        "Recommendation lock: "
        f"{bool(stability_check.get('lock_recommendations', False))} "
        f"(status={stability_check.get('status')})"
    )
    if response_mode == "verbose":
        print(f"- decisions: {output_dir / 'candidate_decisions.json'}")
        print(f"- capabilities: {output_dir / 'candidate_capabilities.json'}")
        print(f"- validator pack: {output_dir / 'candidate_validator_pack.json'}")
        print(f"- queries: {output_dir / 'candidate_queries.json'}")
        print(f"- backlog: {backlog_path}")
        print(f"- decision memo json: {output_dir / 'decision_memo.json'}")
        print(f"- decision memo markdown: {memo_path}")


if __name__ == "__main__":
    main()
