# Capability Search v2

This repository root is now the v2 workspace.

The previous implementation has been archived in `v1-archived/`.

v2 focuses on orchestration and evidence packaging, not rebuilding search engines
that already exist.

Current lexical baseline uses GitHub code search (or local fallback scanning) while
we wire a dedicated Zoekt adapter behind the same retriever contract.

## v2 Goal

Build a system that helps an AI agent discover and evaluate open-source
implementations of a target capability with auditable, commit-pinned evidence.

## Build-vs-Buy Rules

- Use existing systems for heavy search and indexing primitives (for example,
  Zoekt / GitHub code search behavior), then orchestrate around them.
- Keep retrieval hybrid (lexical + semantic + metadata constraints).
- Preserve immutable provenance for every evidence item.
- Evaluate quality against public human-labeled data when possible
  (CodeSearchNet).

## Repository Layout

- `v1-archived/` - prior experiment and artifacts.
- `docs/v2-orchestration-evidence-plan.md` - day-1 phased implementation plan.
- `docs/codesearchnet-dataset-skeleton-plan.md` - dataset acquisition/index/eval plan.
- `src/v2/` - v2 contracts, provenance utilities, and orchestration skeleton.
- `scripts/run_v2.py` - CLI entrypoint for the v2 skeleton.
- `tests/` - initial smoke tests.

## Quickstart

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/run_v2.py plan
.venv/bin/python scripts/run_v2.py run --query "semantic code search" --top-k 5
.venv/bin/python scripts/run_v2.py run --query "code search" --local-only --top-k 5
.venv/bin/python scripts/run_v2.py evaluate \
  --annotations <path-to-CodeSearchNet-annotationStore.csv> \
  --queries <path-to-CodeSearchNet-queries.csv> \
  --top-k 10 --max-queries 20
```

If `GITHUB_TOKEN` is set, run/evaluate use GitHub API discovery + code search.
If API access is unavailable, discovery falls back to local repositories under
`v1-archived/repos/`.
