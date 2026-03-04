# CodeSearchNet Dataset Skeleton Plan

## Goal

Download and use the real CodeSearchNet data locally (not tracked in git) so v2
can:

1. search against a realistic corpus, and
2. measure retrieval quality against human annotations.

## Storage + Git Hygiene

- Dataset root (local only): `data/external/codesearchnet/`
- Derived indexes (local only): `data/indexes/`
- Both are ignored in `.gitignore`.

## Phase 1 - Acquisition

### Objective

Fetch official CodeSearchNet assets with checksum + resumable download support.

### Deliverables

- `scripts/datasets/fetch_codesearchnet.py`
- `scripts/datasets/manifest_codesearchnet.json`

### Scope

- Download language archives from official S3 links.
- Download evaluation files:
  - `resources/queries.csv`
  - `resources/annotationStore.csv`
- Record local manifest: source URL, file size, sha256, timestamp.

### Done When

- All required files exist under `data/external/codesearchnet/`.
- Manifest verifies integrity.

## Phase 2 - Normalization

### Objective

Convert raw CodeSearchNet JSONL into a v2-ready artifact format.

### Deliverables

- `scripts/datasets/prepare_codesearchnet.py`
- `data/external/codesearchnet/normalized/*.jsonl` (local only)

### Scope

- Parse per-language train/valid/test JSONL files.
- Emit normalized records with fields v2 needs:
  - `repo`, `language`, `path`, `func_name`
  - `code`, `docstring`, `code_tokens`, `docstring_tokens`
  - `sha`, `url`, `partition`
- Add stable `doc_id` normalization keyed to URL path for evaluation joins.

### Done When

- Normalized corpus is generated and sample-validated.
- Row counts match source counts by language/partition.

## Phase 3 - Indexing + Search Integration

### Objective

Make CodeSearchNet queryable via v2 retrieval interfaces.

### Deliverables

- `src/v2/adapters/codesearchnet_store.py`
- `src/v2/adapters/codesearchnet_lexical.py`
- `src/v2/adapters/codesearchnet_semantic.py` (initial baseline)

### Scope

- Build lexical index over normalized function-level content.
- Build semantic embeddings over code/docstring views.
- Expose these via existing contracts (`LexicalRetriever`, `SemanticRetriever`).

### Done When

- `run_v2.py run ... --dataset-root data/external/codesearchnet` returns hits
  from the real corpus.

## Phase 4 - Evaluation Against Annotations

### Objective

Run reproducible retrieval metrics against `annotationStore.csv`.

### Deliverables

- Extend `run_v2.py evaluate` dataset mode for CodeSearchNet.
- `reports/codesearchnet/baseline-<timestamp>.json`
- `reports/codesearchnet/baseline-<timestamp>.md`

### Scope

- Evaluate using `queries.csv` + `annotationStore.csv`.
- Report:
  - `NDCG@10`
  - `MRR@10`
  - `Recall@50`
  - latency breakdown by stage
- Include config snapshot (retriever mode, top-k, corpus slice, filters).

### Done When

- One command produces deterministic metric artifacts.

## Phase 5 - Baseline Comparison Loop

### Objective

Establish first measurable baselines and immediate tuning queue.

### Deliverables

- Baseline matrix:
  - lexical-only
  - semantic-only
  - hybrid (RRF)
- Error bucket report (top misses and false positives).

### Done When

- We can answer: "Which mode performs best now, and why?"

## Initial Command Shape (Planned)

```bash
.venv/bin/python scripts/datasets/fetch_codesearchnet.py \
  --output-root data/external/codesearchnet

.venv/bin/python scripts/datasets/prepare_codesearchnet.py \
  --dataset-root data/external/codesearchnet

.venv/bin/python scripts/run_v2.py run \
  --query "parse json" \
  --dataset-root data/external/codesearchnet \
  --top-k 10

.venv/bin/python scripts/run_v2.py evaluate \
  --annotations data/external/codesearchnet/resources/annotationStore.csv \
  --queries data/external/codesearchnet/resources/queries.csv \
  --dataset-root data/external/codesearchnet \
  --top-k 10 --max-queries 99
```

## Risks to Watch Early

- URL/doc-id normalization mismatches can invalidate metrics.
- Full corpus indexing time can be high; start with one language slice for smoke.
- API-free reproducibility should not depend on GitHub network calls.
