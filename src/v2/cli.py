from __future__ import annotations

import argparse
import json

from .adapters.discovery import GitHubRepoDiscoverer
from .adapters.github_api import GitHubClient
from .adapters.ingestion import RepositoryManifestIngestor
from .adapters.lexical import GitHubCodeSearchLexicalRetriever
from .adapters.packaging import CommitEvidencePackager
from .adapters.ranking import HeuristicEvidenceReranker, ReciprocalRankFusion
from .contracts import QuerySpec
from .evaluation.codesearchnet import CodeSearchNetEvaluator
from .pipeline import (
    NoOpRetriever,
    OrchestrationPipeline,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_v2",
        description="Capability Search v2 orchestration and evidence skeleton",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("plan", help="Print the path to the day-1 plan")

    run_parser = subparsers.add_parser("run", help="Run v2 pipeline skeleton")
    run_parser.add_argument("--query", required=True, help="Capability query")
    run_parser.add_argument("--top-k", type=int, default=10, help="Top-k results")
    run_parser.add_argument("--max-repos", type=int, default=8, help="Max repositories to discover")
    run_parser.add_argument("--per-repo-hits", type=int, default=8, help="Max lexical hits per repository")
    run_parser.add_argument(
        "--local-fallback-dir",
        default="v1-archived/repos",
        help="Directory for local repo fallback when API is unavailable",
    )
    run_parser.add_argument("--local-only", action="store_true", help="Skip GitHub API and use local repos only")
    run_parser.add_argument("--github-token", default=None, help="GitHub token (defaults to GITHUB_TOKEN)")

    eval_parser = subparsers.add_parser("evaluate", help="Run CodeSearchNet evaluation")
    eval_parser.add_argument("--annotations", required=True, help="Path to annotations file")
    eval_parser.add_argument("--queries", default=None, help="Optional path to queries CSV")
    eval_parser.add_argument("--top-k", type=int, default=10, help="Top-k cutoff for NDCG/MRR")
    eval_parser.add_argument("--max-queries", type=int, default=20, help="Maximum queries to evaluate")
    eval_parser.add_argument("--max-repos", type=int, default=8, help="Max repositories to discover per query")
    eval_parser.add_argument("--per-repo-hits", type=int, default=8, help="Max lexical hits per repository")
    eval_parser.add_argument(
        "--local-fallback-dir",
        default="v1-archived/repos",
        help="Directory for local repo fallback when API is unavailable",
    )
    eval_parser.add_argument("--local-only", action="store_true", help="Skip GitHub API and use local repos only")
    eval_parser.add_argument("--github-token", default=None, help="GitHub token (defaults to GITHUB_TOKEN)")

    return parser


def build_pipeline(
    *,
    max_repos: int,
    per_repo_hits: int,
    local_fallback_dir: str,
    local_only: bool,
    github_token: str | None,
) -> OrchestrationPipeline:
    client = GitHubClient(token=github_token)
    return OrchestrationPipeline(
        discoverer=GitHubRepoDiscoverer(
            client,
            max_repos=max_repos,
            local_fallback_dir=local_fallback_dir,
            local_only=local_only,
        ),
        ingestor=RepositoryManifestIngestor(client, max_repos=max_repos),
        lexical=GitHubCodeSearchLexicalRetriever(client, per_repo_hits=per_repo_hits),
        semantic=NoOpRetriever(),
        fuser=ReciprocalRankFusion(),
        reranker=HeuristicEvidenceReranker(),
        packager=CommitEvidencePackager(),
        evaluator=None,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "plan":
        print("docs/v2-orchestration-evidence-plan.md")
        return 0

    if args.command == "run":
        pipeline = build_pipeline(
            max_repos=args.max_repos,
            per_repo_hits=args.per_repo_hits,
            local_fallback_dir=args.local_fallback_dir,
            local_only=args.local_only,
            github_token=args.github_token,
        )
        results = pipeline.run(QuerySpec(text=args.query, top_k=args.top_k))
        rendered = [
            {
                "repo": item.repo,
                "path": item.path,
                "start_line": item.start_line,
                "end_line": item.end_line,
                "score": round(item.score, 6),
                "permalink": item.permalink,
                "reasons": list(item.reasons),
            }
            for item in results
        ]
        print(json.dumps({"query": args.query, "count": len(results), "results": rendered}, indent=2))
        return 0

    if args.command == "evaluate":
        pipeline = build_pipeline(
            max_repos=args.max_repos,
            per_repo_hits=args.per_repo_hits,
            local_fallback_dir=args.local_fallback_dir,
            local_only=args.local_only,
            github_token=args.github_token,
        )
        pipeline.evaluator = CodeSearchNetEvaluator(
            run_query=lambda text, top_k: list(pipeline.run(QuerySpec(text=text, top_k=top_k))),
            queries_path=args.queries,
            top_k=args.top_k,
            max_queries=args.max_queries,
        )
        metrics = pipeline.evaluate(args.annotations)
        print(
            json.dumps(
                {
                    "annotations": args.annotations,
                    "queries": args.queries,
                    "top_k": args.top_k,
                    "max_queries": args.max_queries,
                    "metrics": metrics,
                },
                indent=2,
            )
        )
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
