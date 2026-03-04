from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from .adapters.codesearchnet_lexical import CodeSearchNetLexicalRetriever
from .adapters.codesearchnet_semantic import CodeSearchNetSemanticRetriever
from .adapters.codesearchnet_store import CodeSearchNetStore
from .adapters.discovery import GitHubRepoDiscoverer
from .adapters.github_api import GitHubClient
from .adapters.ingestion import RepositoryManifestIngestor
from .adapters.lexical import GitHubCodeSearchLexicalRetriever
from .adapters.packaging import CommitEvidencePackager
from .adapters.ranking import HeuristicEvidenceReranker, ReciprocalRankFusion
from .contracts import QuerySpec
from .evaluation.codesearchnet import CodeSearchNetEvaluator
from .pipeline import NoOpDiscoverer, NoOpIngestor, NoOpRetriever, OrchestrationPipeline


RETRIEVAL_MODES = ("lexical", "semantic", "hybrid")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_v2",
        description="Capability Search v2 orchestration and evidence engine",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("plan", help="Print the path to the day-1 plan")

    run_parser = subparsers.add_parser("run", help="Run v2 pipeline")
    run_parser.add_argument("--query", required=True, help="Capability query")
    run_parser.add_argument("--top-k", type=int, default=10, help="Top-k results")
    run_parser.add_argument("--mode", choices=RETRIEVAL_MODES, default="hybrid", help="Retrieval mode")
    run_parser.add_argument("--dataset-root", default=None, help="CodeSearchNet dataset root")
    run_parser.add_argument("--languages", default=None, help="Comma-separated language filters")
    run_parser.add_argument("--max-docs", type=int, default=0, help="Optional corpus size cap")
    run_parser.add_argument("--max-repos", type=int, default=8, help="Max repositories to discover")
    run_parser.add_argument("--per-repo-hits", type=int, default=8, help="Max lexical hits per repository")
    run_parser.add_argument(
        "--local-fallback-dir",
        default="v1-archived/repos",
        help="Directory for local repo fallback when API is unavailable",
    )
    run_parser.add_argument("--local-only", action="store_true", help="Skip GitHub API and use local repos only")
    run_parser.add_argument("--github-token", default=None, help="GitHub token (defaults to GITHUB_TOKEN)")

    eval_parser = subparsers.add_parser("evaluate", help="Run retrieval evaluation")
    eval_parser.add_argument("--annotations", default=None, help="Path to annotations file")
    eval_parser.add_argument("--queries", default=None, help="Path to queries CSV")
    eval_parser.add_argument("--top-k", type=int, default=10, help="Top-k cutoff for NDCG/MRR")
    eval_parser.add_argument("--recall-k", type=int, default=50, help="Recall cutoff")
    eval_parser.add_argument("--max-queries", type=int, default=20, help="Maximum queries to evaluate")
    eval_parser.add_argument("--mode", choices=RETRIEVAL_MODES, default="hybrid", help="Retrieval mode")
    eval_parser.add_argument(
        "--all-modes",
        action="store_true",
        help="Evaluate lexical, semantic, and hybrid in one command",
    )
    eval_parser.add_argument("--dataset-root", default=None, help="CodeSearchNet dataset root")
    eval_parser.add_argument("--languages", default=None, help="Comma-separated language filters")
    eval_parser.add_argument("--max-docs", type=int, default=0, help="Optional corpus size cap")
    eval_parser.add_argument("--report-dir", default="reports/codesearchnet", help="Directory for JSON/MD reports")
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
    mode: str,
    dataset_root: str | None,
    languages: list[str],
    max_docs: int,
    max_repos: int,
    per_repo_hits: int,
    local_fallback_dir: str,
    local_only: bool,
    github_token: str | None,
) -> OrchestrationPipeline:
    if dataset_root:
        store = CodeSearchNetStore(
            dataset_root,
            languages=languages,
            max_docs=max_docs,
        )
        lexical = CodeSearchNetLexicalRetriever(store) if mode in {"lexical", "hybrid"} else NoOpRetriever()
        semantic = CodeSearchNetSemanticRetriever(store) if mode in {"semantic", "hybrid"} else NoOpRetriever()
        return OrchestrationPipeline(
            discoverer=NoOpDiscoverer(),
            ingestor=NoOpIngestor(),
            lexical=lexical,
            semantic=semantic,
            fuser=ReciprocalRankFusion(),
            reranker=HeuristicEvidenceReranker(),
            packager=CommitEvidencePackager(),
            evaluator=None,
        )

    client = GitHubClient(token=github_token)
    lexical = GitHubCodeSearchLexicalRetriever(client, per_repo_hits=per_repo_hits)
    return OrchestrationPipeline(
        discoverer=GitHubRepoDiscoverer(
            client,
            max_repos=max_repos,
            local_fallback_dir=local_fallback_dir,
            local_only=local_only,
        ),
        ingestor=RepositoryManifestIngestor(client, max_repos=max_repos),
        lexical=lexical if mode in {"lexical", "hybrid"} else NoOpRetriever(),
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
            mode=args.mode,
            dataset_root=args.dataset_root,
            languages=_parse_csv(args.languages),
            max_docs=args.max_docs,
            max_repos=args.max_repos,
            per_repo_hits=args.per_repo_hits,
            local_fallback_dir=args.local_fallback_dir,
            local_only=args.local_only,
            github_token=args.github_token,
        )
        results, stage_latency_ms = pipeline.run_with_trace(QuerySpec(text=args.query, top_k=args.top_k))
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
        print(
            json.dumps(
                {
                    "query": args.query,
                    "mode": args.mode,
                    "dataset_root": args.dataset_root,
                    "count": len(results),
                    "stage_latency_ms": stage_latency_ms,
                    "results": rendered,
                },
                indent=2,
            )
        )
        return 0

    if args.command == "evaluate":
        try:
            annotations, queries = _resolve_eval_paths(
                annotations=args.annotations,
                queries=args.queries,
                dataset_root=args.dataset_root,
            )
        except ValueError as exc:
            parser.error(str(exc))
        modes = list(RETRIEVAL_MODES) if args.all_modes else [args.mode]
        by_mode: dict[str, dict[str, object]] = {}
        for mode in modes:
            by_mode[mode] = _evaluate_mode(
                mode=mode,
                annotations=annotations,
                queries=queries,
                top_k=args.top_k,
                recall_k=args.recall_k,
                max_queries=args.max_queries,
                dataset_root=args.dataset_root,
                languages=_parse_csv(args.languages),
                max_docs=args.max_docs,
                max_repos=args.max_repos,
                per_repo_hits=args.per_repo_hits,
                local_fallback_dir=args.local_fallback_dir,
                local_only=args.local_only,
                github_token=args.github_token,
            )

        payload: dict[str, object] = {
            "annotations": annotations,
            "queries": queries,
            "top_k": args.top_k,
            "recall_k": args.recall_k,
            "max_queries": args.max_queries,
            "dataset_root": args.dataset_root,
            "languages": _parse_csv(args.languages),
            "max_docs": args.max_docs,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "results": by_mode,
        }

        report_paths = _write_reports(args.report_dir, payload)
        payload["report_json"] = str(report_paths[0])
        payload["report_markdown"] = str(report_paths[1])
        print(json.dumps(payload, indent=2))
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


def _evaluate_mode(
    *,
    mode: str,
    annotations: str,
    queries: str | None,
    top_k: int,
    recall_k: int,
    max_queries: int,
    dataset_root: str | None,
    languages: list[str],
    max_docs: int,
    max_repos: int,
    per_repo_hits: int,
    local_fallback_dir: str,
    local_only: bool,
    github_token: str | None,
) -> dict[str, object]:
    pipeline = build_pipeline(
        mode=mode,
        dataset_root=dataset_root,
        languages=languages,
        max_docs=max_docs,
        max_repos=max_repos,
        per_repo_hits=per_repo_hits,
        local_fallback_dir=local_fallback_dir,
        local_only=local_only,
        github_token=github_token,
    )
    pipeline.evaluator = CodeSearchNetEvaluator(
        run_query=lambda text, run_top_k: pipeline.run_with_trace(QuerySpec(text=text, top_k=run_top_k)),
        queries_path=queries,
        top_k=top_k,
        recall_k=recall_k,
        max_queries=max_queries,
    )
    metrics = pipeline.evaluate(annotations)
    return {
        "mode": mode,
        "metrics": metrics,
    }


def _resolve_eval_paths(*, annotations: str | None, queries: str | None, dataset_root: str | None) -> tuple[str, str | None]:
    resolved_annotations = annotations
    resolved_queries = queries
    if dataset_root:
        base = Path(dataset_root) / "resources"
        if not resolved_annotations:
            resolved_annotations = str(base / "annotationStore.csv")
        if not resolved_queries:
            resolved_queries = str(base / "queries.csv")
    if not resolved_annotations:
        raise ValueError("--annotations is required when --dataset-root is not provided")
    return resolved_annotations, resolved_queries


def _write_reports(report_dir: str, payload: dict[str, object]) -> tuple[Path, Path]:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target_dir = Path(report_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    json_path = target_dir / f"baseline-{timestamp}.json"
    markdown_path = target_dir / f"baseline-{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    markdown_path.write_text(_render_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def _render_markdown(payload: dict[str, object]) -> str:
    lines = [
        "## Summary",
        f"- Generated at: {payload.get('generated_at')}",
        f"- Annotations: `{payload.get('annotations')}`",
        f"- Queries: `{payload.get('queries')}`",
        f"- Dataset root: `{payload.get('dataset_root')}`",
        f"- top_k={payload.get('top_k')} recall_k={payload.get('recall_k')} max_queries={payload.get('max_queries')}",
        "",
        "## Metrics by Mode",
    ]

    results = payload.get("results")
    if not isinstance(results, dict):
        return "\n".join(lines)

    for mode, report in results.items():
        lines.append(f"### {mode}")
        metrics = report.get("metrics") if isinstance(report, dict) else None
        if not isinstance(metrics, dict):
            lines.append("- No metrics")
            continue
        for key, value in metrics.items():
            if key == "latency_ms" and isinstance(value, dict):
                lines.append("- latency_ms:")
                for stage, stage_latency in value.items():
                    lines.append(f"  - {stage}: {stage_latency:.3f}")
                continue
            lines.append(f"- {key}: {value}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
