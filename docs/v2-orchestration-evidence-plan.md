# v2 Orchestration + Evidence Plan (Today)

## Context

The project is reset to a v2 direction after research on existing systems
(GitHub code search, Zoekt, Sourcegraph, CodeSearchNet and related IR work).

The core decision is to **orchestrate proven components** and focus custom
engineering effort on evidence quality, provenance, and evaluation.

## Day-1 Outcomes

By end of day, we want:

1. A clean v2 repository shape with v1 archived.
2. Stable contracts for a modular retrieval and evidence pipeline.
3. A runnable skeleton CLI that exercises the v2 flow shape.
4. A concrete next implementation queue grounded in measurable quality.

## Implementation Status

- Phase 0 complete: repository archived into `v1-archived/`.
- Phase 1 complete: contracts and runnable CLI skeleton in place.
- Phase 2 in progress: GitHub discovery + lexical retrieval + evidence packaging wired.
- Phase 4 bootstrap complete: `evaluate` now supports CodeSearchNet-style CSV input.

## Non-Goals for Today

- Training a new retrieval model.
- Building a custom search engine or index format.
- Distributed infra and production deployment.

## Architecture Principles

1. **Evidence-first**: every output must include immutable provenance.
2. **Hybrid retrieval**: lexical + semantic + metadata constraints.
3. **Replaceable adapters**: discovery/index/retrieval/rerank components are
   swappable behind contracts.
4. **Quality over volume**: filter forks/archives/generated/vendored noise early.
5. **Measured progress**: evaluate against public annotations (CodeSearchNet).

## Phased Implementation (Today)

### Phase 0 - Restructure and Archive

- Move current implementation and artifacts into `v1-archived/`.
- Keep repository root as the canonical v2 workspace.
- Preserve old assets as reference, not as active runtime.

Done when:
- Root has only v2 docs/skeleton/runtime files.
- v1 code and notes are isolated under `v1-archived/`.

### Phase 1 - Contracts and Skeleton

- Define stage contracts in `src/v2/contracts.py`:
  - discovery
  - ingestion
  - lexical retrieval
  - semantic retrieval
  - rank fusion
  - reranking
  - evidence packaging
  - evaluation
- Add a minimal orchestration pipeline that wires these contracts.
- Add CLI command surface for `plan`, `run`, and `evaluate`.

Done when:
- `scripts/run_v2.py` executes successfully.
- Contract types are importable and testable.

### Phase 2 - Baseline Retrieval Loop

- Implement a first pass with one lexical adapter and one discovery adapter.
- Return snippet-level rows with path + line spans + commit permalink.
- Apply initial metadata filters (fork/archive and generated/vendored heuristics).

Done when:
- A query returns ranked, auditable evidence entries.

### Phase 3 - Hybrid + Helpfulness Reranking

- Add semantic retrieval adapter for symbol/snippet chunks.
- Fuse dense/sparse with RRF.
- Add helpfulness features:
  - symbol-definition boosts
  - examples/tests/config boosts
  - generic mention penalties

Done when:
- Hybrid outperforms lexical-only on internal seed queries.

### Phase 4 - CodeSearchNet Evaluation Harness

- Ingest CodeSearchNet query/annotation resources.
- Compute `NDCG@10`, `MRR@10`, `Recall@50`, and latency by stage.
- Export JSON and markdown reports for regression tracking.

Done when:
- One command generates reproducible evaluation metrics.

## Build-vs-Buy Mapping

- **Use existing**:
  - code search/indexing primitives (Zoekt/GitHub-like workflows)
  - parser ecosystem (Tree-sitter)
  - public benchmark assets (CodeSearchNet annotations)
- **Build custom**:
  - cross-source orchestration
  - evidence schema and provenance packaging
  - policy-aware filtering and reranking
  - evaluation runner for project-specific decisions

## Immediate Next Queue

1. Add a Zoekt-backed lexical adapter and make backend selection configurable.
2. Add discovery budgets/stopping controls (API call budgets + novelty thresholds).
3. Add semantic chunk store and keep RRF fusion as the merge strategy.
4. Run CodeSearchNet baseline and publish the first metric report artifact.
