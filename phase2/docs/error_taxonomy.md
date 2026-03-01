# Error Taxonomy

Use this taxonomy consistently during benchmark review.

## Classes

- `extraction_fp`
  - A card should not exist.
  - Example: repo tagged `api_service` with no route declarations.

- `extraction_fn`
  - A valid card is missing.
  - Example: known CLI framework repo without `cli_tooling` card.

- `ranking_fp`
  - Card exists but is ranked too high for a query.
  - Example: generic ingestion card outranks explicit OCR card.

- `ranking_fn`
  - Relevant card exists but is ranked too low.

- `filter_error`
  - Structured filter parsing/matching failed.
  - Example: `license=apache` query returns GPL-only results.

- `evidence_gap`
  - Card has weak/non-auditable evidence paths.

- `unknown`
  - Catch-all; should be minimized.

## Severity guide

- `high`: changes top-1 or blocks target workflow.
- `medium`: appears in top-5 and degrades trust.
- `low`: appears at lower rank or edge query only.

## Resolution preference

1. Fix extraction quality first.
2. Then tune ranking.
3. Then broaden recall.
