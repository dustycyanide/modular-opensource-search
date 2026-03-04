#!/usr/bin/env python3
"""Generate challenge cards from a phase2 benchmark report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate challenge cards from report")
    parser.add_argument("--report", required=True, help="Phase2 report JSON")
    parser.add_argument("--mode", default="hybrid", choices=["lexical", "semantic", "hybrid"], help="Mode to inspect")
    parser.add_argument("--output", required=True, help="Output markdown file")
    parser.add_argument("--max-cards", type=int, default=20, help="Maximum cards")
    return parser.parse_args()


def severity_for_errors(error_counts: dict[str, int]) -> str:
    weighted = (
        error_counts.get("ranking_fp", 0) * 3
        + error_counts.get("ranking_fn", 0) * 3
        + error_counts.get("extraction_fp", 0) * 2
        + error_counts.get("extraction_fn", 0) * 2
        + error_counts.get("filter_error", 0) * 2
        + error_counts.get("evidence_gap", 0)
    )
    if weighted >= 8:
        return "high"
    if weighted >= 4:
        return "medium"
    return "low"


def main() -> None:
    args = parse_args()
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cards = []
    for query in report.get("query_results", []):
        mode_data = query["mode_results"][args.mode]
        error_counts = mode_data.get("error_counts", {})
        total_errors = sum(error_counts.values())
        if total_errors <= 0:
            continue

        failure_type = max(error_counts.items(), key=lambda item: item[1])[0]
        severity = severity_for_errors(error_counts)
        observed = [f"{row['repo']}:{row['capability']}" for row in mode_data.get("results", [])[:5]]
        expected_repos = query.get("expected_repos", [])
        expected_caps = query.get("expected_capabilities", [])

        cards.append(
            {
                "id": f"AUTO-{query['id']}",
                "query": query["query"],
                "family": query["family"],
                "mode": args.mode,
                "failure_type": failure_type,
                "severity": severity,
                "expected_repos": expected_repos,
                "expected_capabilities": expected_caps,
                "observed": observed,
                "errors": mode_data.get("errors", [])[:5],
            }
        )

    cards.sort(key=lambda card: (card["severity"], len(card["errors"])), reverse=True)
    cards = cards[: args.max_cards]

    lines = ["# Generated Challenge Cards", "", f"Mode: `{args.mode}`", ""]
    for card in cards:
        lines.append(f"## {card['id']}")
        lines.append("")
        lines.append(f"- query: `{card['query']}`")
        lines.append(f"- family: `{card['family']}`")
        lines.append(f"- mode: `{card['mode']}`")
        lines.append(f"- failure_type: `{card['failure_type']}`")
        lines.append(f"- severity: `{card['severity']}`")
        lines.append(f"- expected_repos: {card['expected_repos']}")
        lines.append(f"- expected_capabilities: {card['expected_capabilities']}")
        lines.append(f"- observed_top_k: {card['observed']}")
        lines.append("- error_samples:")
        for error in card["errors"]:
            detail = error.get("detail", "")
            lines.append(f"  - {error.get('type', 'unknown')}: {detail}")
        lines.append("")

    output_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    print(f"Wrote challenge cards: {output_path}")


if __name__ == "__main__":
    main()
