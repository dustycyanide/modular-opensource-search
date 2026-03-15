# Implementation Plan

**Ticket:** v2-readiness
**Date:** 2026-03-11

## Overview

This plan closes the gap between the current v2 prototype and a version that can be used for serious internal testing. The main work is to replace manifest-only live ingestion with real code/document chunks, add a real semantic retriever for live runs, improve discovery and reranking quality, and define readiness gates using the existing evaluation harness.

## Current State

The codebase already has a runnable orchestrator, evidence packaging, a GitHub/local lexical path, and a CodeSearchNet evaluation harness.

- `src/v2/pipeline.py` — runs the staged pipeline and records per-stage latency.
- `src/v2/cli.py` — builds either a live pipeline or a CodeSearchNet-backed evaluation pipeline.
- `src/v2/adapters/discovery.py` — discovers GitHub repos or local fallback repos.
- `src/v2/adapters/ingestion.py` — only emits repo manifests with commit SHA and metadata; it does not ingest files into chunks.
- `src/v2/adapters/lexical.py` — performs GitHub code search or local file scans and extracts best-match snippets.
- `src/v2/adapters/ranking.py` — applies RRF plus light path-based boosts.
- `src/v2/adapters/codesearchnet_store.py` — builds a lexical index over the normalized CodeSearchNet corpus and uses token overlap as its current semantic baseline.
- `src/v2/evaluation/codesearchnet.py` — computes NDCG, MRR, recall, latency, and error buckets.

## What We're NOT Doing

- Building a custom distributed search engine or new index format.
- Training a new retrieval model.
- Shipping a production deployment stack for Zoekt, Sourcegraph, or OpenSSF Scorecard.
- Adding an LLM reranker before the non-LLM retrieval and ranking basics are working.

---

## Phase 1: Real Live Ingestion and Chunking

### Goal

Replace the current manifest-only live ingestor with a chunking pipeline that produces `ArtifactChunk` records from real repository files. This phase comes first because live semantic retrieval, better reranking, and evidence quality all depend on having an actual chunk corpus.

### Changes

#### 1. Modify: `src/v2/adapters/ingestion.py`

**What:** Replace `RepositoryManifestIngestor` with a chunk-producing ingestor that can read local repositories directly and fetch GitHub file trees for remote repositories.

**Current code for context:**
```python
# Current code at src/v2/adapters/ingestion.py:15
def ingest(self, candidates):
    manifests: list[ArtifactChunk] = []
    for candidate in list(candidates)[: self.max_repos]:
        commit_sha = self._resolve_head_sha(candidate)
        metadata = dict(candidate.metadata)
        metadata.setdefault("repo_url", self._resolve_repo_url(candidate))
        manifests.append(
            ArtifactChunk(
                repo=f"{candidate.owner}/{candidate.name}" if candidate.owner != "local" else candidate.name,
                commit_sha=commit_sha,
                path="",
                language="repo",
                symbol=None,
                start_line=1,
                end_line=1,
                content="",
                metadata=metadata,
            )
        )
    return manifests
```

**New/modified:**
```python
from dataclasses import dataclass
from pathlib import Path

from ..contracts import ArtifactChunk, RepoCandidate
from .chunking import ChunkingConfig, RepositoryChunkBuilder
from .github_api import GitHubClient


@dataclass(frozen=True)
class IngestionConfig:
    max_repos: int = 8
    max_files_per_repo: int = 400
    max_file_bytes: int = 250_000
    chunk_lines: int = 40
    overlap_lines: int = 8


class RepositoryChunkIngestor:
    def __init__(self, client: GitHubClient, *, config: IngestionConfig | None = None) -> None:
        self.client = client
        self.config = config or IngestionConfig()
        self.chunk_builder = RepositoryChunkBuilder(
            ChunkingConfig(
                max_file_bytes=self.config.max_file_bytes,
                chunk_lines=self.config.chunk_lines,
                overlap_lines=self.config.overlap_lines,
            )
        )

    def ingest(self, candidates):
        chunks: list[ArtifactChunk] = []
        for candidate in list(candidates)[: self.config.max_repos]:
            repo_chunks = self._ingest_repo(candidate)
            chunks.extend(repo_chunks[: self.config.max_files_per_repo * 8])
        return chunks
```

**Implementation notes:**
- Keep `_resolve_head_sha()` and `_resolve_repo_url()` from the current file.
- Add `_ingest_local_repo()` for local repos under `v1-archived/repos`.
- Add `_ingest_github_repo()` that resolves the commit SHA, lists files from the Git tree, fetches text content, and builds chunks.
- Preserve repo-level metadata on every produced chunk: `repo_url`, `language`, `topics`, `pushed_at`, `is_fork`, `is_archived`.

**Pattern reference:** Follow `src/v2/adapters/lexical.py:184-240` for local file iteration and `src/v2/adapters/lexical.py:161-182` for GitHub file fetch behavior.

#### 2. Create: `src/v2/adapters/chunking.py`

**What:** Centralize file filtering, language detection, chunk construction, and chunk metadata so both ingestion and local lexical fallback use the same file-selection logic.

**New file:**
```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..contracts import ArtifactChunk
from .lexical import TEXT_EXTENSIONS, is_noise_path, language_from_path


@dataclass(frozen=True)
class ChunkingConfig:
    max_file_bytes: int = 250_000
    chunk_lines: int = 40
    overlap_lines: int = 8
    min_nonblank_lines: int = 3


class RepositoryChunkBuilder:
    def __init__(self, config: ChunkingConfig) -> None:
        self.config = config

    def should_include_path(self, rel_path: str) -> bool:
        suffix = Path(rel_path).suffix.lower()
        return suffix in TEXT_EXTENSIONS and not is_noise_path(rel_path)

    def build_chunks(
        self,
        *,
        repo: str,
        commit_sha: str,
        rel_path: str,
        text: str,
        base_metadata: dict[str, object],
    ) -> list[ArtifactChunk]:
        lines = text.splitlines()
        if len([line for line in lines if line.strip()]) < self.config.min_nonblank_lines:
            return []

        chunks: list[ArtifactChunk] = []
        step = max(1, self.config.chunk_lines - self.config.overlap_lines)
        for start in range(0, len(lines), step):
            window = lines[start : start + self.config.chunk_lines]
            if not window:
                break
            start_line = start + 1
            end_line = start + len(window)
            chunks.append(
                ArtifactChunk(
                    repo=repo,
                    commit_sha=commit_sha,
                    path=rel_path,
                    language=language_from_path(rel_path),
                    symbol=None,
                    start_line=start_line,
                    end_line=end_line,
                    content="\n".join(window),
                    metadata=dict(base_metadata),
                )
            )
            if end_line >= len(lines):
                break
        return chunks
```

**Pattern reference:** Reuse constants from `src/v2/adapters/lexical.py:11-47`.

#### 3. Modify: `src/v2/adapters/github_api.py`

**What:** Add Git tree listing and blob/file helpers so live ingestion does not need to repurpose the lexical adapter’s private fetch path.

**New/modified:**
```python
class GitHubClient:
    ...

    def list_tree(self, owner: str, repo: str, ref: str) -> list[dict[str, object]]:
        payload = self.get_json(
            f"/repos/{owner}/{repo}/git/trees/{ref}",
            params={"recursive": 1},
        )
        if not isinstance(payload, dict):
            return []
        tree = payload.get("tree", [])
        return tree if isinstance(tree, list) else []

    def get_text_file(self, owner: str, repo: str, path: str, *, ref: str | None = None) -> str | None:
        payload = self.get_json(
            f"/repos/{owner}/{repo}/contents/{path}",
            params={"ref": ref} if ref else None,
        )
        ...
```

**Implementation notes:**
- Keep `get_json()` as the low-level primitive.
- Add explicit handling for truncated tree responses so the ingestor can stop cleanly and record that in metadata.
- Make sure every new helper raises `GitHubApiError` consistently on HTTP failures.

#### 4. Modify: `src/v2/cli.py`

**What:** Add ingestion controls to the `run` and `evaluate` commands and wire the new ingestor.

**New/modified:**
```python
run_parser.add_argument("--max-files-per-repo", type=int, default=400)
run_parser.add_argument("--max-file-bytes", type=int, default=250000)
run_parser.add_argument("--chunk-lines", type=int, default=40)
run_parser.add_argument("--overlap-lines", type=int, default=8)
```

```python
ingestor = RepositoryChunkIngestor(
    client,
    config=IngestionConfig(
        max_repos=max_repos,
        max_files_per_repo=max_files_per_repo,
        max_file_bytes=max_file_bytes,
        chunk_lines=chunk_lines,
        overlap_lines=overlap_lines,
    ),
)
```

#### 5. Create: `tests/test_ingestion.py`

**What:** Lock down local chunking behavior before semantic retrieval is added.

**New file:**
```python
from pathlib import Path

from v2.adapters.ingestion import IngestionConfig, RepositoryChunkIngestor
from v2.adapters.github_api import GitHubClient
from v2.contracts import QuerySpec, RepoCandidate


def test_local_ingestor_emits_chunks_for_source_file(tmp_path: Path) -> None:
    repo = tmp_path / "demo"
    (repo / ".git").mkdir(parents=True)
    (repo / "src").mkdir()
    (repo / "src" / "parser.py").write_text(
        "def parse_json(payload):\n    return json.loads(payload)\n",
        encoding="utf-8",
    )

    ingestor = RepositoryChunkIngestor(
        GitHubClient(token="test"),
        config=IngestionConfig(max_repos=1, max_files_per_repo=20, chunk_lines=20),
    )
    chunks = ingestor.ingest(
        [
            RepoCandidate(
                host="local",
                owner="local",
                name="demo",
                clone_url=str(repo),
                metadata={"local_path": str(repo), "repo_url": "https://github.com/acme/demo"},
            )
        ]
    )

    assert chunks
    assert chunks[0].path == "src/parser.py"
    assert "parse_json" in chunks[0].content
```

### Verification

- [ ] `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src .venv/bin/pytest -q tests/test_ingestion.py tests/test_lexical.py`
- [ ] `.venv/bin/python scripts/run_v2.py run --query "semantic code search" --local-only --top-k 5 --max-files-per-repo 200`
- [ ] Manually inspect returned results and confirm `path`, `start_line`, `end_line`, and `permalink` now point to real source/doc chunks instead of repo-level manifests.

---

## Phase 2: Real Semantic Retrieval for Live and Dataset Runs

### Goal

Replace the token-overlap semantic baseline with embedding-based retrieval and make the live pipeline use semantic retrieval instead of `NoOpRetriever`. This phase is what turns v2 from lexical-only plumbing into a true hybrid retriever.

### Dependencies

Phase 1 must be complete so the live path has a real chunk corpus to embed and search.

### Changes

#### 1. Create: `src/v2/adapters/embedding_index.py`

**What:** Add a shared in-memory embedding index used by both the live semantic adapter and the CodeSearchNet store.

**New file:**
```python
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from fastembed import TextEmbedding


@dataclass(frozen=True)
class EmbeddingConfig:
    model_name: str = "BAAI/bge-base-en-v1.5"
    batch_size: int = 64


class EmbeddingIndex:
    def __init__(self, config: EmbeddingConfig | None = None) -> None:
        self.config = config or EmbeddingConfig()
        self.model = TextEmbedding(model_name=self.config.model_name, lazy_load=True)
        self._vectors: np.ndarray | None = None

    def build(self, texts: list[str]) -> None:
        vectors = np.vstack(list(self.model.passage_embed(texts))).astype("float32")
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        self._vectors = vectors / np.clip(norms, 1e-12, None)

    def search(self, query_text: str, *, top_k: int) -> list[tuple[int, float]]:
        if self._vectors is None:
            return []
        query_vector = np.asarray(next(self.model.query_embed([query_text])), dtype="float32")
        query_vector = query_vector / max(np.linalg.norm(query_vector), 1e-12)
        scores = self._vectors @ query_vector
        if top_k <= 0:
            return []
        candidate_indexes = np.argpartition(scores, -top_k)[-top_k:]
        ranked = sorted(
            ((int(index), float(scores[index])) for index in candidate_indexes),
            key=lambda item: item[1],
            reverse=True,
        )
        return ranked
```

**Implementation notes:**
- Keep this abstraction small; it only needs build/search for now.
- Do not add persistence until the in-memory path is validated.
- Use query/document-specific embedding methods from `fastembed` (`query_embed`, `passage_embed`) instead of plain `embed`.

#### 2. Create: `src/v2/adapters/semantic.py`

**What:** Add a real semantic retriever for live `ArtifactChunk` corpora.

**New file:**
```python
from __future__ import annotations

from ..contracts import QuerySpec, ScoredChunk
from .embedding_index import EmbeddingIndex


class EmbeddingSemanticRetriever:
    def __init__(self, *, candidate_multiplier: int = 5) -> None:
        self.candidate_multiplier = candidate_multiplier
        self.index = EmbeddingIndex()

    def retrieve(self, query: QuerySpec, corpus):
        if not corpus:
            return []

        texts = [_semantic_text(chunk) for chunk in corpus]
        self.index.build(texts)
        top_k = max(query.top_k * self.candidate_multiplier, query.top_k)

        out: list[ScoredChunk] = []
        for doc_index, score in self.index.search(query.text, top_k=top_k):
            chunk = corpus[doc_index]
            out.append(
                ScoredChunk(
                    chunk=chunk,
                    score=score,
                    source="embedding_semantic",
                    reasons=("semantic_embedding_match",),
                )
            )
        return out


def _semantic_text(chunk) -> str:
    parts = [chunk.path, chunk.language, chunk.content]
    return "\n".join(part for part in parts if part)
```

**Pattern reference:** Mirror the shape of `src/v2/adapters/codesearchnet_semantic.py:8-45`.

#### 3. Modify: `src/v2/adapters/codesearchnet_store.py`

**What:** Replace the current token-overlap semantic search with the shared embedding index so the benchmark path and the live path use the same core semantic behavior.

**Current code for context:**
```python
# Current code at src/v2/adapters/codesearchnet_store.py:133
def semantic_search(self, query_text: str, *, top_k: int):
    self.ensure_loaded()
    query_tokens = set(tokenize(query_text))
    if not query_tokens:
        return []

    scored: list[tuple[int, float]] = []
    for index, semantic_tokens in enumerate(self._semantic_sets):
        ...
```

**New/modified:**
```python
from .embedding_index import EmbeddingConfig, EmbeddingIndex


class CodeSearchNetStore:
    def __init__(...):
        ...
        self._semantic_index: EmbeddingIndex | None = None
        self._semantic_texts: list[str] = []

    def _build_semantic_index(self) -> None:
        self._semantic_texts = [
            "\n".join(
                part for part in [doc.func_name, doc.path, doc.docstring, doc.code[:1200]] if part
            )
            for doc in self.documents
        ]
        self._semantic_index = EmbeddingIndex(EmbeddingConfig(model_name="BAAI/bge-base-en-v1.5"))
        self._semantic_index.build(self._semantic_texts)

    def semantic_search(self, query_text: str, *, top_k: int):
        self.ensure_loaded()
        if self._semantic_index is None:
            return []
        hits = self._semantic_index.search(query_text, top_k=top_k)
        return [
            (self.documents[index], score, ("semantic_embedding_match",))
            for index, score in hits
        ]
```

#### 4. Modify: `src/v2/cli.py`

**What:** Wire the live pipeline to the real semantic retriever and expose model configuration.

**New/modified:**
```python
from .adapters.semantic import EmbeddingSemanticRetriever

run_parser.add_argument("--embedding-model", default="BAAI/bge-base-en-v1.5")
```

```python
semantic = EmbeddingSemanticRetriever() if mode in {"semantic", "hybrid"} else NoOpRetriever()
```

**Implementation notes:**
- The live path currently sets `semantic=NoOpRetriever()` in `build_pipeline()`. Remove that once `EmbeddingSemanticRetriever` is in place.
- If model warmup is too expensive, add lazy construction on first `retrieve()` call rather than on `__init__`.

#### 5. Create: `tests/test_semantic.py`

**What:** Add deterministic smoke tests around the semantic adapter and store integration.

**New file:**
```python
from v2.adapters.semantic import EmbeddingSemanticRetriever
from v2.contracts import ArtifactChunk, QuerySpec


def test_embedding_semantic_retriever_prefers_parse_json_chunk() -> None:
    corpus = [
        ArtifactChunk(
            repo="demo",
            commit_sha="abc123",
            path="src/parser.py",
            language="Python",
            symbol=None,
            start_line=1,
            end_line=5,
            content="def parse_json(payload): return json.loads(payload)",
        ),
        ArtifactChunk(
            repo="demo",
            commit_sha="abc123",
            path="src/config.py",
            language="Python",
            symbol=None,
            start_line=1,
            end_line=5,
            content="def load_yaml(path): return yaml.safe_load(path.read_text())",
        ),
    ]

    retriever = EmbeddingSemanticRetriever(candidate_multiplier=2)
    hits = retriever.retrieve(QuerySpec(text="parse json", top_k=1), corpus)
    assert hits
    assert hits[0].chunk.path == "src/parser.py"
```

### Verification

- [ ] `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src .venv/bin/pytest -q tests/test_semantic.py tests/test_codesearchnet_adapters.py tests/test_codesearchnet_evaluator.py`
- [ ] `.venv/bin/python scripts/run_v2.py run --query "parse json" --dataset-root data/external/codesearchnet --mode hybrid --top-k 3 --max-docs 1000`
- [ ] `.venv/bin/python scripts/run_v2.py run --query "semantic code search" --local-only --mode hybrid --top-k 5 --max-files-per-repo 200`
- [ ] Confirm stage latency now includes non-zero `semantic` time in live runs and that live `hybrid` results differ from lexical-only results.

---

## Phase 3: Discovery Budgets, Quality Filters, and Better Helpfulness Ranking

### Goal

Improve the quality of candidate repositories and evidence ordering so the system is more likely to surface usable implementations instead of broad topical matches or doc-only noise.

### Dependencies

Phases 1 and 2 must be complete so discovery and ranking operate on real evidence chunks.

### Changes

#### 1. Modify: `src/v2/adapters/discovery.py`

**What:** Add explicit discovery budgets, query variants, and repo-quality filtering.

**New/modified:**
```python
from dataclasses import dataclass


@dataclass(frozen=True)
class DiscoveryConfig:
    max_repos: int = 8
    max_api_queries: int = 3
    min_stars: int = 5
    exclude_archived: bool = True
    exclude_forks: bool = True
```

```python
def _candidate_queries(self, query: QuerySpec) -> list[str]:
    base = query.text.strip()
    return [
        base,
        f"{base} in:description",
        f"{base} topic:{_topic_slug(base)}",
    ]
```

**Implementation notes:**
- Dedupe by `owner/name` across query variants.
- Carry repo-level reasons into `RepoCandidate.metadata["discovery_reasons"]`.
- Record whether results came from GitHub or local fallback so later evaluation can explain failures.

#### 2. Modify: `src/v2/adapters/ranking.py`

**What:** Make reranking aware of source-code usefulness instead of just path boosts.

**New/modified:**
```python
class HeuristicEvidenceReranker:
    def rerank(self, query: QuerySpec, chunks):
        query_tokens = {token for token in query.text.lower().split() if len(token) >= 3}
        reranked: list[ScoredChunk] = []
        for item in chunks:
            path = item.chunk.path.lower()
            content = item.chunk.content.lower()
            score = item.score
            reasons = list(item.reasons)

            if item.chunk.language != "Text":
                score += 0.08
                reasons.append("source_code_boost")
            if any(token in path for token in query_tokens):
                score += 0.06
                reasons.append("path_query_overlap")
            if "def " in content or "class " in content or "func " in content:
                score += 0.05
                reasons.append("definition_like_boost")
            if path.endswith(("readme.md", ".md")) and item.chunk.language == "Text":
                score -= 0.04
                reasons.append("docs_only_penalty")
            ...
```

**Implementation notes:**
- Keep existing boosts for `examples/`, `tests/`, `docs/`, and runnable files.
- Add penalties for trivial text-only matches and oversized generic files.
- Keep the reranker deterministic so CodeSearchNet metrics remain reproducible.

#### 3. Modify: `src/v2/adapters/packaging.py`

**What:** Preserve more explanation metadata in every evidence item.

**New/modified:**
```python
metadata={
    "query": query.text,
    "source": item.source,
    "language": chunk.language,
    "repo_topics": chunk.metadata.get("topics", []),
    "discovery_reasons": chunk.metadata.get("discovery_reasons", []),
    "chunk_kind": chunk.metadata.get("chunk_kind"),
}
```

#### 4. Create: `tests/test_ranking.py`

**What:** Add tests for path boosts and doc-only penalties so ranking behavior does not drift.

### Verification

- [ ] `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src .venv/bin/pytest -q tests/test_ranking.py tests/test_lexical.py`
- [ ] `.venv/bin/python scripts/run_v2.py run --query "oauth callback handler" --local-only --mode hybrid --top-k 10`
- [ ] Manually confirm that source files and examples rank ahead of generic READMEs for the same repo.

---

## Phase 4: Evaluation, Readiness Gates, and Operator UX

### Goal

Turn the current benchmark harness into a real readiness signal for ongoing development and dogfooding.

### Dependencies

All retrieval-path changes should be in place so the evaluation can measure the right system.

### Changes

#### 1. Modify: `src/v2/cli.py`

**What:** Add a smoke mode for evaluation and a `--fail-below-*` readiness gate.

**New/modified:**
```python
eval_parser.add_argument("--fail-below-ndcg", type=float, default=None)
eval_parser.add_argument("--fail-below-recall", type=float, default=None)
eval_parser.add_argument("--smoke", action="store_true", help="Run a fast bounded evaluation")
```

```python
if args.fail_below_ndcg is not None:
    hybrid_ndcg = _mode_metric(by_mode, mode="hybrid", key=f"ndcg@{args.top_k}")
    if hybrid_ndcg is not None and hybrid_ndcg < args.fail_below_ndcg:
        return 1
```

#### 2. Modify: `src/v2/evaluation/codesearchnet.py`

**What:** Emit a small set of benchmark counters that are useful for development decisions.

**New/modified:**
```python
return {
    "query_count": evaluated_queries,
    ndcg_key: _safe_mean(ndcg_scores),
    mrr_key: _safe_mean(mrr_scores),
    recall_key: _safe_mean(recall_scores),
    "latency_ms": {...},
    "error_buckets": ...,
    "queries_with_any_relevant_hit": sum(1 for value in mrr_scores if value > 0.0),
    "queries_with_zero_hits": sum(1 for row in query_diagnostics if not row["top_predicted_ids"]),
}
```

#### 3. Modify: `README.md`

**What:** Change the quickstart to reflect the actual readiness workflow.

**New/modified:**
```markdown
## Readiness Workflow

1. Run unit tests
2. Run local-only dogfood queries
3. Run bounded CodeSearchNet evaluation
4. Inspect latest report in `reports/codesearchnet/`
```

#### 4. Create: `scripts/run_v2_smoke.sh`

**What:** Add one command for local validation before each iteration.

**New file:**
```bash
#!/usr/bin/env bash
set -euo pipefail

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src .venv/bin/pytest -q
.venv/bin/python scripts/run_v2.py run --query "semantic code search" --local-only --mode hybrid --top-k 5
.venv/bin/python scripts/run_v2.py evaluate \
  --dataset-root data/external/codesearchnet \
  --all-modes \
  --top-k 10 \
  --max-queries 25 \
  --max-docs 5000 \
  --fail-below-ndcg 0.05 \
  --fail-below-recall 0.08
```

### Verification

- [ ] `bash scripts/run_v2_smoke.sh`
- [ ] Confirm the command exits non-zero when readiness thresholds are missed.
- [ ] Confirm a new JSON/Markdown report appears under `reports/codesearchnet/`.

---

## Code Patterns Reference

### Pipeline Assembly
**Source:** `src/v2/cli.py:86-133`
```python
def build_pipeline(...):
    if dataset_root:
        store = CodeSearchNetStore(...)
        lexical = CodeSearchNetLexicalRetriever(store) if mode in {"lexical", "hybrid"} else NoOpRetriever()
        semantic = CodeSearchNetSemanticRetriever(store) if mode in {"semantic", "hybrid"} else NoOpRetriever()
        return OrchestrationPipeline(...)

    client = GitHubClient(token=github_token)
    lexical = GitHubCodeSearchLexicalRetriever(client, per_repo_hits=per_repo_hits)
    return OrchestrationPipeline(...)
```

### Stage Timing
**Source:** `src/v2/pipeline.py:37-70`
```python
def run_with_trace(self, query: QuerySpec) -> tuple[Sequence[EvidenceItem], dict[str, float]]:
    ...
    lexical_hits = self.lexical.retrieve(query, corpus)
    ...
    semantic_hits = self.semantic.retrieve(query, corpus)
    ...
    packaged = self.packager.package(query, reranked[: query.top_k])
```

### CodeSearchNet Lexical Indexing
**Source:** `src/v2/adapters/codesearchnet_store.py:98-131`
```python
def lexical_search(self, query_text: str, *, top_k: int):
    self.ensure_loaded()
    query_tokens = tokenize(query_text)
    ...
    for token in query_tokens:
        postings = self._lexical_postings.get(token)
        ...
```

## Key Files

### Created
- `src/v2/adapters/chunking.py` — shared file filtering and chunk construction (Phase 1)
- `src/v2/adapters/embedding_index.py` — shared embedding search primitive (Phase 2)
- `src/v2/adapters/semantic.py` — live semantic retriever (Phase 2)
- `tests/test_ingestion.py` — live chunk ingestion tests (Phase 1)
- `tests/test_semantic.py` — semantic retriever smoke tests (Phase 2)
- `tests/test_ranking.py` — reranking regression tests (Phase 3)
- `scripts/run_v2_smoke.sh` — one-command local validation (Phase 4)

### Modified
- `src/v2/adapters/ingestion.py` — move from repo manifests to real chunk ingestion (Phase 1)
- `src/v2/adapters/github_api.py` — add tree and text-file helpers (Phase 1)
- `src/v2/cli.py` — new ingestion/embedding/readiness flags and live semantic wiring (Phases 1, 2, 4)
- `src/v2/adapters/codesearchnet_store.py` — replace token-overlap semantic search with embeddings (Phase 2)
- `src/v2/adapters/ranking.py` — add code usefulness signals and penalties (Phase 3)
- `src/v2/adapters/packaging.py` — preserve richer evidence metadata (Phase 3)
- `src/v2/evaluation/codesearchnet.py` — emit readiness counters (Phase 4)
- `README.md` — update quickstart to a readiness workflow (Phase 4)

## Risks & Gotchas

- **Embedding cold start** — The first semantic run will download and initialize the model; keep smoke runs bounded with `--max-docs` until retrieval quality is acceptable.
- **GitHub tree truncation** — Large repos may return incomplete recursive trees; record truncation in metadata and keep the per-repo file budget explicit.
- **Memory pressure** — Building embeddings for the entire CodeSearchNet corpus in one shot may be expensive; use `--max-docs` during iteration and only widen once the ranking logic is stable.
- **False confidence from README hits** — Better ingestion alone will not fix ranking quality; Phase 3 is required to avoid doc-heavy top results.
- **Benchmarks can stay weak after plumbing is fixed** — If hybrid quality remains low after Phase 2, inspect the error buckets before adding more retrieval complexity.
