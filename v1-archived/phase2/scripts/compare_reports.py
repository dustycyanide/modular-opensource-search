#!/usr/bin/env python3
"""Compare two phase2 benchmark reports and print metric deltas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare phase2 reports")
    parser.add_argument("--baseline", required=True, help="Baseline report JSON")
    parser.add_argument("--candidate", required=True, help="Candidate report JSON")
    return parser.parse_args()


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def delta(a: float, b: float) -> float:
    return round(b - a, 3)


def format_delta(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.3f}"


def main() -> None:
    args = parse_args()
    baseline = load(args.baseline)
    candidate = load(args.candidate)

    print("Overall mode deltas")
    for mode, base_metrics in baseline["aggregates"]["by_mode"].items():
        cand_metrics = candidate["aggregates"]["by_mode"].get(mode)
        if not cand_metrics:
            continue
        print(
            f"- {mode}: "
            f"repo_precision {format_delta(delta(base_metrics['avg_repo_precision'], cand_metrics['avg_repo_precision']))}, "
            f"repo_coverage {format_delta(delta(base_metrics['avg_repo_coverage'], cand_metrics['avg_repo_coverage']))}, "
            f"cap_precision {format_delta(delta(base_metrics['avg_capability_precision'], cand_metrics['avg_capability_precision']))}, "
            f"errors {format_delta(delta(base_metrics['avg_errors_total'], cand_metrics['avg_errors_total']))}"
        )

    print("\nMode-family deltas")
    base_family = baseline["aggregates"]["by_mode_family"]
    cand_family = candidate["aggregates"]["by_mode_family"]
    for mode, families in base_family.items():
        for family, base_metrics in families.items():
            cand_metrics = cand_family.get(mode, {}).get(family)
            if not cand_metrics:
                continue
            print(
                f"- {mode}/{family}: "
                f"repo_precision {format_delta(delta(base_metrics['avg_repo_precision'], cand_metrics['avg_repo_precision']))}, "
                f"repo_coverage {format_delta(delta(base_metrics['avg_repo_coverage'], cand_metrics['avg_repo_coverage']))}, "
                f"cap_precision {format_delta(delta(base_metrics['avg_capability_precision'], cand_metrics['avg_capability_precision']))}, "
                f"errors {format_delta(delta(base_metrics['avg_errors_total'], cand_metrics['avg_errors_total']))}"
            )


if __name__ == "__main__":
    main()
