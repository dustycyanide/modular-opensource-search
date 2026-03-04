# Iterative 5-Repo Test Notes (Baseline)

This captures the quick "1 -> 2 -> 5 repos" viability run before structural
validator + embedding upgrades. See `V2_NOTES.md` for the updated pass.

## Runner

- Script: `iterative_repos_test.py`
- Report: `data/iterative_report.json`
- DB: `data/capabilities_iterative.db`

## Repositories

- OCRmyPDF
- requests
- flask
- click
- pytesseract

## Query snapshots (final 5-repo state)

- `python ocr document pipeline async`
  - Top results are meaningful (`pytesseract` + `OCRmyPDF` OCR cards).
  - Also returns weaker false positives (`requests`/`click` document pipeline).
  - Repo precision@5 (human-labeled expected repos) = `0.60`.
  - Expected-repo coverage = `1.00`.

- `python api service`
  - Finds `flask` correctly.
  - Also mislabels `click` as API service (false positive).
  - Repo precision@5 = `0.50`.
  - Expected-repo coverage = `1.00`.

- `python cli command tooling`
  - Finds `click` and `flask` correctly.
  - Some over-triggering remains due to keyword overlap.
  - Repo precision@5 = `0.75`.
  - Expected-repo coverage = `1.00`.

## Takeaway

- The capability-card concept works enough to continue.
- Current extraction is still heuristic-heavy and noisy.
- Next step should prioritize stronger evidence checks (symbol patterns,
  framework-specific signatures, and stage-level constraints).
