# Phase 2 Challenge Cards

Status board for process experiments.

## CH-CLI-001

- query: `python cli command tooling`
- problem: recall regression in strict validator mode; `click` and `typer` may be missed
- type: `extraction_fn`
- severity: high
- hypothesis: strict evidence currently favors app repos over framework repos
- proposed change: add framework-specific signatures for CLI library internals

## CH-DATA-001

- query: `python orm migration database`
- problem: `database_persistence` cards often absent
- type: `extraction_fn`
- severity: high
- hypothesis: rule requires SQL verbs that are uncommon in ORM-centric repos
- proposed change: allow ORM model/session signatures to satisfy second group

## CH-ASYNC-001

- query: `python async queue worker`
- problem: inconsistent queue detection across celery/rq repos
- type: `extraction_fn`
- severity: medium
- hypothesis: evidence spread across config + decorators + docs
- proposed change: add cross-file queue identity signatures (`shared_task`, worker command entrypoints)

## CH-OCR-001

- query: `apache python ocr processing`
- problem: license filters can over-prune if license parsing is coarse
- type: `filter_error`
- severity: medium
- hypothesis: license parser only checks a few canonical patterns
- proposed change: add SPDX/license-file heuristics and fallback detection in `pyproject.toml`

## CH-NEG-001

- query: `python http client library`
- problem: benchmark currently maps to weak capability expectations
- type: `mixed`
- severity: medium
- hypothesis: capability taxonomy does not include `http_client`
- proposed change: add capability and validators or explicitly mark query unsupported

## CH-EVIDENCE-001

- query: all
- problem: some cards include generic evidence files
- type: `evidence_gap`
- severity: medium
- hypothesis: evidence collection does not prioritize entrypoints/symbol definitions
- proposed change: weight evidence toward `src/*` definitions and route/task decorators

## CH-SSR-001

- query: `server side rendering document app`
- problem: no representation for UI architecture constraints
- type: `extraction_fn`
- severity: high
- hypothesis: current capability schema is backend-heavy
- proposed change: add UI capability family and architecture fields (SSR/CSR/ISR)

## CH-PROVENANCE-001

- query: all
- problem: missing explicit provenance scoring in output
- type: `mixed`
- severity: low
- hypothesis: confidence score under-represents evidence quality
- proposed change: add provenance score (tests + license + entrypoint evidence density)
