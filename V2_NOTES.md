# V2 Noise-Reduction Notes

## What changed

- Added structural validators per capability in `capability_index.py`.
- Added semantic embeddings with `fastembed` (`all-MiniLM-L6-v2`).
- Added retrieval modes: `lexical`, `semantic`, `hybrid`.
- Added hybrid rank that combines semantic score, lexical rank, confidence,
  and structural validation score.

## Why this matters

- The old extraction was mostly keyword/heuristic based.
- Structural rules gate capability cards before they enter the index.
- This removes several false positives (for example `click` incorrectly tagged
  as API service in earlier runs).

## Commands used

```bash
.venv/bin/python capability_index.py --db ./data/capabilities_v2.db init
.venv/bin/python capability_index.py --db ./data/capabilities_v2.db ingest --repo-path ./repos/OCRmyPDF
.venv/bin/python capability_index.py --db ./data/capabilities_v2.db ingest --repo-path ./repos/requests
.venv/bin/python capability_index.py --db ./data/capabilities_v2.db ingest --repo-path ./repos/flask
.venv/bin/python capability_index.py --db ./data/capabilities_v2.db ingest --repo-path ./repos/click
.venv/bin/python capability_index.py --db ./data/capabilities_v2.db ingest --repo-path ./repos/pytesseract
.venv/bin/python iterative_modes_test.py
```

## Outcome (5 repos)

- API query now returns only `flask` API service card.
- OCR query reliably returns `OCRmyPDF` and `pytesseract`.
- False positives are lower than v1.
- Trade-off: recall dropped for CLI (`click` not surfaced as a capability card,
  only OCRmyPDF appears for CLI query in current rules).

## Next tuning target

- Improve `cli_tooling` structural rule so framework repos like `click` can be
  recognized without reopening API-like false positives.
