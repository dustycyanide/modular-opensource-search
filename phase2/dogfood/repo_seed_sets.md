# Repo Seed Sets for Dogfooding

Start with capability-focused cohorts, not random popular repos.

## Wave 1: Calibration set (high signal, already aligned)

Use this to stabilize extraction and ranking behavior.

- API: `flask`, `fastapi`
- CLI: `click`, `typer`
- Async: `celery`, `rq`
- OCR/document: `OCRmyPDF`, `pytesseract`
- Persistence: `sqlalchemy`, `django`
- Contrast: `requests` (HTTP client, useful negative for API queries)

## Wave 2: Capability-mining set (integration candidates)

Use this to harvest implementation patterns we may integrate.

- Code parsing and structure: `tree-sitter/tree-sitter`, `semgrep/semgrep`, `ast-grep/ast-grep`
- Search and indexing: `sourcegraph/zoekt`, `apache/lucene`, `tantivy-search/tantivy`
- Retrieval infra: `qdrant/qdrant`, `milvus-io/milvus`, `chroma-core/chroma`
- Evaluation and ML ops: `evidentlyai/evidently`, `langchain-ai/openevals`
- Pipeline orchestration: `prefecthq/prefect`, `apache/airflow`

## Wave 3: Stress/contrast set (false-positive resistance)

Use this to harden precision.

- Large general libraries: `numpy/numpy`, `pandas-dev/pandas`
- Tooling with overlapping keywords: `psf/black`, `pytest-dev/pytest`
- Docs-heavy repos: `facebook/docusaurus`

## Repo quality bar

Prioritize repos that meet most of the following:

- Active maintenance (recent commits in last 6 months).
- Clear architecture and docs (readme + developer docs).
- Strong test coverage or CI signals.
- Permissive licensing when integration/reuse is likely.
- Distinct capability signal (not broad "does everything" monorepos only).
