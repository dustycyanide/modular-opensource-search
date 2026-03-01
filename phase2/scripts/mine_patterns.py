#!/usr/bin/env python3
"""Mine token-level pattern hints from benchmark true/false results.

This is intentionally lightweight and intended for validator-pack tuning.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
CODE_EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".java", ".rb", ".rs", ".php"}
STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "return",
    "class",
    "def",
    "self",
    "true",
    "false",
    "none",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mine candidate patterns from benchmark report")
    parser.add_argument("--report", required=True, help="Phase2 report JSON")
    parser.add_argument("--repos-root", default="repos", help="Local repos root directory")
    parser.add_argument("--mode", default="hybrid", choices=["lexical", "semantic", "hybrid"], help="Mode to inspect")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--max-files-per-repo", type=int, default=60, help="Max files to scan per repo")
    return parser.parse_args()


def iter_code_files(repo_path: Path, max_files: int):
    count = 0
    for path in repo_path.rglob("*"):
        if count >= max_files:
            break
        if not path.is_file():
            continue
        if path.suffix.lower() not in CODE_EXTS:
            continue
        if "/.git/" in path.as_posix():
            continue
        count += 1
        yield path


def extract_tokens_from_repo(repo_path: Path, max_files: int) -> Counter:
    token_counter: Counter = Counter()
    for code_file in iter_code_files(repo_path, max_files=max_files):
        try:
            text = code_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for token in TOKEN_PATTERN.findall(text):
            tok = token.lower()
            if tok in STOPWORDS:
                continue
            token_counter[tok] += 1
    return token_counter


def score_tokens(pos_counter: Counter, neg_counter: Counter, min_pos_freq: int = 4) -> list[dict]:
    rows = []
    all_tokens = set(pos_counter.keys()) | set(neg_counter.keys())
    for token in all_tokens:
        pos = pos_counter[token]
        neg = neg_counter[token]
        if pos < min_pos_freq:
            continue
        ratio = (pos + 1.0) / (neg + 1.0)
        rows.append({"token": token, "pos": pos, "neg": neg, "ratio": round(ratio, 3)})
    rows.sort(key=lambda row: (row["ratio"], row["pos"]), reverse=True)
    return rows


def main() -> None:
    args = parse_args()
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    repos_root = Path(args.repos_root).resolve()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    by_family = defaultdict(lambda: {"pos_repos": set(), "neg_repos": set()})

    for query_result in report["query_results"]:
        family = query_result["family"]
        mode_data = query_result["mode_results"][args.mode]
        expected_repos = set(query_result.get("expected_repos", []))
        for row in mode_data.get("results", []):
            repo = row["repo"]
            if repo in expected_repos:
                by_family[family]["pos_repos"].add(repo)
            else:
                by_family[family]["neg_repos"].add(repo)

    family_candidates = {}
    repo_token_cache: dict[str, Counter] = {}

    for family, bucket in by_family.items():
        pos_counter: Counter = Counter()
        neg_counter: Counter = Counter()

        for repo in sorted(bucket["pos_repos"]):
            if repo not in repo_token_cache:
                repo_path = repos_root / repo
                repo_token_cache[repo] = extract_tokens_from_repo(repo_path, args.max_files_per_repo) if repo_path.exists() else Counter()
            pos_counter.update(repo_token_cache[repo])

        for repo in sorted(bucket["neg_repos"]):
            if repo not in repo_token_cache:
                repo_path = repos_root / repo
                repo_token_cache[repo] = extract_tokens_from_repo(repo_path, args.max_files_per_repo) if repo_path.exists() else Counter()
            neg_counter.update(repo_token_cache[repo])

        scored = score_tokens(pos_counter, neg_counter)
        family_candidates[family] = {
            "positive_repos": sorted(bucket["pos_repos"]),
            "negative_repos": sorted(bucket["neg_repos"]),
            "candidate_tokens": scored[:30],
        }

    payload = {
        "source_report": str(Path(args.report).resolve()),
        "mode": args.mode,
        "families": family_candidates,
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote pattern candidates: {output_path}")


if __name__ == "__main__":
    main()
