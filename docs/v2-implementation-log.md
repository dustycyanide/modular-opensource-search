# Plan Implementation Log: v2 Readiness

**Ticket:** v2-readiness
**Started:** 2026-03-14

---

## Phase 1: Real Live Ingestion and Chunking

**Status:** COMPLETED

### Work Completed

- Added shared chunking utilities for file filtering, language detection, and chunk construction — `src/v2/adapters/chunking.py`
- Added repeatable tests for path filtering, overlap windows, and low-signal file skipping — `tests/test_chunking.py`
- Added a new chunk-producing ingestor for local and GitHub repos while preserving the existing manifest ingestor during migration — `src/v2/adapters/ingestion.py`
- Added repeatable local git-repo ingestion tests with no mocks — `tests/test_ingestion.py`
- Added GitHub client helpers for tree listing and text-file decoding — `src/v2/adapters/github_api.py`
- Added HTTP-server-backed tests for GitHub helpers and remote ingestion with no mocks — `tests/test_github_api.py`
- Updated lexical retrieval to operate on ingested chunk corpora as well as repo-manifest inputs — `src/v2/adapters/lexical.py`
- Wired chunk ingestion controls through the CLI and validated a local-only pipeline run — `src/v2/cli.py`
- Added a minimal local pipeline integration test that exercises discovery → ingestion → lexical → packaging using a temp git repo — `tests/test_pipeline_local.py`

### Validation

- [x] `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src .venv/bin/pytest -q tests/test_chunking.py tests/test_ingestion.py tests/test_github_api.py tests/test_lexical.py tests/test_pipeline_local.py` → PASSED
- [x] `.venv/bin/python scripts/run_v2.py run --query "semantic code search" --local-only --top-k 5 --max-files-per-repo 200` → PASSED

### Deviations

- **Phase 1 migration strategy**: Kept `RepositoryManifestIngestor` in place temporarily while adding `RepositoryChunkIngestor` so lower-layer tests could land without breaking the live pipeline mid-phase.

### Next Phase Readiness

Phase 1 gate passed. The live pipeline now ingests real chunks and can score them lexically end to end. It is safe to proceed to semantic retrieval.

---

## Phase 2: Real Semantic Retrieval for Live and Dataset Runs

**Status:** COMPLETED

### Work Completed

- Added a shared embedding index backed by `fastembed` — `src/v2/adapters/embedding_index.py`
- Added a live semantic retriever over ingested chunk corpora — `src/v2/adapters/semantic.py`
- Replaced the CodeSearchNet token-overlap semantic baseline with the embedding index — `src/v2/adapters/codesearchnet_store.py`
- Wired the live pipeline to use semantic retrieval in `semantic` and `hybrid` modes — `src/v2/cli.py`
- Added repeatable real-model semantic smoke tests — `tests/test_semantic.py`
- Extended local pipeline coverage to assert semantic-mode evidence and non-zero semantic timing — `tests/test_pipeline_local.py`

### Validation

- [x] `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src .venv/bin/pytest -q tests/test_semantic.py tests/test_codesearchnet_adapters.py tests/test_pipeline_local.py tests/test_codesearchnet_evaluator.py` → PASSED

### Deviations

- **Phase 2 gate shape**: Used bounded real-model tests and the local semantic pipeline test as the phase gate instead of corpus-wide semantic CLI runs. The larger runs work as integration/perf checks but are too expensive to serve as repeatable layer tests.

### Next Phase Readiness

Phase 2 gate passed. Semantic retrieval is now present in the live pipeline and the CodeSearchNet-backed store. It is safe to proceed to ranking, packaging, and evaluation layers.

---

## Phase 3: Discovery, Fusion, Reranking, and Packaging Quality

**Status:** COMPLETED

### Work Completed

- Updated RRF to preserve reasons from multiple contributing ranked lists — `src/v2/adapters/ranking.py`
- Added code-usefulness reranking signals and penalties for doc-only matches — `src/v2/adapters/ranking.py`
- Added regression tests for fusion explanation preservation and reranker ordering — `tests/test_ranking.py`
- Extended packaged evidence metadata with topics, discovery reasons, and chunk kind — `src/v2/adapters/packaging.py`
- Added packaging contract tests, including local evidence without permalinks — `tests/test_packaging.py`

### Validation

- [x] `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src .venv/bin/pytest -q tests/test_ranking.py tests/test_packaging.py tests/test_provenance.py` → PASSED

### Deviations

None.

### Next Phase Readiness

Phase 3 gate passed. Fused results now preserve layered explanations, reranking is more useful for implementation-focused evidence, and packaging covers both GitHub-backed and local evidence.

---

## Phase 4: Evaluation and Repeatable Layer Smoke Testing

**Status:** COMPLETED

### Work Completed

- Added evaluator counters for queries with any relevant hit and queries with zero hits — `src/v2/evaluation/codesearchnet.py`
- Added evaluator coverage for the new counters — `tests/test_codesearchnet_evaluator.py`
- Added an ordered smoke script that runs the layer tests from low-level adapters up through evaluation — `scripts/run_v2_smoke.sh`

### Validation

- [x] `bash scripts/run_v2_smoke.sh` → PASSED
- [x] `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src .venv/bin/pytest -q` → PASSED

### Deviations

- **Smoke workflow**: The repeatable smoke path is test-first rather than query-first. This matches the current goal better because the semantic CLI path is still expensive on larger corpora and should not be the primary fast feedback loop.

### Next Phase Readiness

All current layers are covered by repeatable tests and the full suite is passing.
