# Capability Search Experiment v1

This project is a capability search engine for open-source repositories.
It scans local repos, detects what they can do (for example OCR processing,
API service, and CLI tooling), and converts those signals into structured
capability cards backed by file-path evidence.

Those capability cards act as an intermediate representation (IR) layer used
for hybrid retrieval that combines lexical search, semantic embeddings, and
confidence/validation scoring.

This experiment now includes a deeper v2-style pass:

- Evidence-backed capability extraction.
- Structural validators per capability (to reduce false positives).
- True embedding-based semantic retrieval using `fastembed`.
- Hybrid ranking that combines lexical, semantic, confidence, and validation score.

## What this does

- Ingest local repositories.
- Build capability cards with metadata and file-path evidence.
- Validate cards with structural rules (route signatures, OCR indicators, CLI signatures, etc).
- Store card embeddings in SQLite.
- Query with one of 3 modes:
  - `lexical` (FTS-focused)
  - `semantic` (embedding-focused)
  - `hybrid` (combined ranker)

## Files

- `capability_index.py` - main CLI for init/ingest/search/list.
- `iterative_repos_test.py` - baseline iterative run.
- `iterative_modes_test.py` - iterative lexical vs semantic vs hybrid comparison.
- `V2_NOTES.md` - noise-reduction findings and trade-offs.
- `phase2/` - process-lab assets for benchmark, mining, and challenge loops.
- `data/*.db` - local SQLite DB files.
- `data/*report*.json` - run reports.

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Quick start

```bash
.venv/bin/python capability_index.py --db ./data/capabilities.db init
.venv/bin/python capability_index.py --db ./data/capabilities.db ingest --repo-path ./repos/OCRmyPDF
.venv/bin/python capability_index.py --db ./data/capabilities.db ingest --repo-path ./repos/flask
.venv/bin/python capability_index.py --db ./data/capabilities.db search --query "python api service" --k 5 --mode lexical
.venv/bin/python capability_index.py --db ./data/capabilities.db search --query "python api service" --k 5 --mode semantic
.venv/bin/python capability_index.py --db ./data/capabilities.db search --query "python api service" --k 5 --mode hybrid
```

## Iterative tests

```bash
.venv/bin/python iterative_repos_test.py
.venv/bin/python iterative_modes_test.py
```

## Notes

- This is still an experiment, not production-grade static analysis.
- Structural validation helps, but noisy cards can still appear.
- Embeddings improve semantic matching, but extraction quality still dominates final precision.
