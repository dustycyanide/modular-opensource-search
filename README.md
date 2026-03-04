# Modular Open Source — Capability Search

## Why This Exists

Agents tend to rebuild everything from scratch. That then requires us to re-verify that the thing they built actually works.

What humans tend to do is pull together building blocks and pieces of things they already know work. Open source code — especially code that is widely used and adopted — is a great source of pre-verified building blocks. These are patterns and implementations that have already been tested in production, reviewed by communities, and proven at scale.

If we can give agents access to this, we can harness their ability to search patterns, understand those patterns, and then implement those patterns into our codebase — rather than having them create everything from scratch and leaving us to verify the result ourselves.

That is what this project does.

---

## What It Does

Capability Search is a multi-repository search tool for agents. Given a description of a capability you want to build, it searches across open source repositories to find existing implementations of that capability, packages the relevant code as auditable evidence, and returns it to the agent for review and potential adoption into the target codebase.

The design principle is the same as the one guiding the whole project: don't rebuild what already exists. The system orchestrates around proven search and indexing primitives (Zoekt, GitHub code search) rather than reimplementing them.

---

## How It Works

### In Production (Agent Workflow)

1. **Specify** — the agent describes the types of repositories to target and the capability it is looking for.
2. **Discover** — the system finds relevant repositories via GitHub API or a local fallback directory.
3. **Ingest** — repository manifests are indexed into a searchable corpus.
4. **Retrieve** — the corpus is searched using lexical matching, semantic similarity, or both.
5. **Rank & Fuse** — results from multiple retrieval strategies are merged using Reciprocal Rank Fusion and reranked with heuristic signals.
6. **Package** — the top results are packaged as commit-pinned evidence items with permalinks and reasoning, ready for the agent to review and integrate.

### Retrieval Modes

| Mode | Description |
|------|-------------|
| `lexical` | Token-based search over code symbols, identifiers, and documentation |
| `semantic` | Embedding-based similarity search for conceptual matching |
| `hybrid` | Fused combination of both, giving the broadest and most accurate coverage |

### Pipeline Stages

```
query → discover → ingest → [lexical + semantic] → fuse → rerank → package → evidence
```

Each stage is timed independently, so bottlenecks are visible in every run's output.

---

## Accuracy Baseline

The system is evaluated against the [CodeSearchNet](https://github.com/github/CodeSearchNet) dataset, a public benchmark of human-annotated code search queries with relevance judgments across multiple programming languages.

Evaluation produces per-mode metrics and a diagnostic report:

- **NDCG@k** — normalized discounted cumulative gain, measures ranking quality
- **MRR@k** — mean reciprocal rank, measures how quickly the first relevant result appears
- **Recall@k** — fraction of all relevant documents recovered in the top-k
- **Error buckets** — top missed queries, false positives, and commonly-missed documents for targeted tuning

Reports are written to `reports/codesearchnet/` as both JSON and Markdown.

---

## Repository Layout

```
src/v2/
  contracts.py              — protocol interfaces for every pipeline stage
  pipeline.py               — OrchestrationPipeline orchestrator
  cli.py                    — CLI entry point (plan / run / evaluate)
  provenance.py             — commit-pinned provenance utilities
  adapters/
    discovery.py            — GitHub repo discovery
    ingestion.py            — repository manifest ingestion
    lexical.py              — GitHub code search lexical retriever
    ranking.py              — RRF fuser + heuristic reranker
    packaging.py            — evidence packager
    codesearchnet_store.py  — CodeSearchNet corpus loader
    codesearchnet_lexical.py  — lexical retriever over CodeSearchNet corpus
    codesearchnet_semantic.py — semantic retriever over CodeSearchNet corpus
  evaluation/
    codesearchnet.py        — NDCG / MRR / Recall evaluator

scripts/
  run_v2.py                 — CLI wrapper
  datasets/
    fetch_codesearchnet.py  — download CodeSearchNet dataset
    prepare_codesearchnet.py — prepare dataset for evaluation

docs/
  v2-orchestration-evidence-plan.md       — phased implementation plan
  codesearchnet-dataset-skeleton-plan.md  — dataset acquisition and eval plan

reports/codesearchnet/   — generated baseline reports (JSON + Markdown)
v1-archived/             — prior experiment and artifacts
```

---

## Quickstart

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

### Run a capability search

```bash
# Against GitHub (requires GITHUB_TOKEN)
.venv/bin/python scripts/run_v2.py run \
  --query "semantic code search" \
  --mode hybrid \
  --top-k 5

# Local repos only (no API needed)
.venv/bin/python scripts/run_v2.py run \
  --query "semantic code search" \
  --local-only \
  --top-k 5
```

### Run against the CodeSearchNet corpus

```bash
# Download the dataset
.venv/bin/python scripts/datasets/fetch_codesearchnet.py \
  --output-root data/external/codesearchnet \
  --languages python

# Prepare it
.venv/bin/python scripts/datasets/prepare_codesearchnet.py \
  --dataset-root data/external/codesearchnet

# Search
.venv/bin/python scripts/run_v2.py run \
  --query "parse json" \
  --dataset-root data/external/codesearchnet \
  --mode hybrid \
  --top-k 10
```

### Evaluate retrieval quality

```bash
# All three modes in one run, writes reports to reports/codesearchnet/
.venv/bin/python scripts/run_v2.py evaluate \
  --dataset-root data/external/codesearchnet \
  --all-modes \
  --top-k 10 \
  --max-queries 99
```

---

## Configuration Reference

### `run` flags

| Flag | Default | Description |
|------|---------|-------------|
| `--query` | required | Capability description to search for |
| `--mode` | `hybrid` | `lexical`, `semantic`, or `hybrid` |
| `--top-k` | `10` | Number of results to return |
| `--dataset-root` | — | Path to a prepared CodeSearchNet corpus |
| `--languages` | — | Comma-separated language filter (e.g. `python,go`) |
| `--max-repos` | `8` | Max repositories to discover per query |
| `--per-repo-hits` | `8` | Max lexical hits per repository |
| `--local-only` | `false` | Skip GitHub API, use local repos under `--local-fallback-dir` |
| `--local-fallback-dir` | `v1-archived/repos` | Directory scanned when API is unavailable |
| `--github-token` | `$GITHUB_TOKEN` | GitHub personal access token |

### `evaluate` flags

Inherits all `run` flags, plus:

| Flag | Default | Description |
|------|---------|-------------|
| `--all-modes` | `false` | Evaluate lexical, semantic, and hybrid in a single pass |
| `--recall-k` | `50` | Recall cutoff |
| `--max-queries` | `20` | Queries to evaluate |
| `--error-bucket-limit` | `10` | Max entries per error bucket in the report |
| `--report-dir` | `reports/codesearchnet` | Output directory for JSON and Markdown reports |

---

## Environment

Set `GITHUB_TOKEN` to enable GitHub API discovery and code search. Without it, the pipeline falls back to local repositories under `v1-archived/repos/`.

```bash
export GITHUB_TOKEN=ghp_...
```
