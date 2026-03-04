# Adopt/Adapt Implementation Plan

This plan implements the current recommendations:

- Adopt: `repo_indexing_pipeline`
- Adopt: `semantic_retrieval_stack`
- Adapt: `evaluation_harness`

## Outcome we want

By the end of this plan, the project should:

1. Ingest repositories with better provenance and scan controls.
2. Retrieve capabilities more reliably with stronger semantic ranking behavior.
3. Evaluate changes through a project-specific harness with clear pass/fail gates.

## Scope and non-goals

In scope:

- Changes in `capability_index.py` for capability extraction, scoring, and ranking.
- Benchmark and report tooling in `phase2/scripts/`.
- Discovery/decision memo continuity in `phase3/` and `phase4/` outputs.

Out of scope for this cycle:

- New deployment services.
- UI/product surface changes.
- Full structured filtering rollout (currently rejected).

## Workstream A - Adopt `repo_indexing_pipeline`

Why adopt now:

- Directly aligned with the core value of this project (indexing + evidence-backed retrieval).
- Strong enough signal and clear implementation path.

### A1. Add first-class capability support

- Add `repo_indexing_pipeline` to `CAPABILITIES` in `capability_index.py`.
- Add structural validator rule to `DEFAULT_CAPABILITY_STRUCTURAL_RULES`.
- Add capability-specific input/output descriptions in `build_cards()`.

### A2. Improve indexing provenance and scan controls

- Add repo scan policy config (include extensions + ignore directories + size limits).
- Track ingest quality signals per repo/profile:
  - `files_scanned`
  - `code_files_scanned`
  - `docs_or_tests_skipped`
  - `scan_limit_hit`
- Persist these signals in `repos.summary` and card `quality_signals_json`.

### A3. Strengthen evidence quality

- Annotate evidence with source kind (code/doc/test) before merging evidence paths.
- Prefer entrypoint and core-module evidence over docs/tests when building cards.
- Add evidence-density and code-evidence ratio to card quality signals.

### A4. Add benchmark coverage

- Add 2-3 `repo_indexing_pipeline` queries in `phase2/benchmark/queries.json`.
- Ensure contrast repos are included (at least one should not rank high).

### A5. Acceptance gate

- New capability appears in top-5 for its own queries.
- No >0.05 precision regression in existing families.
- Evidence quality fields are present and non-empty for matched cards.

## Workstream B - Adopt `semantic_retrieval_stack`

Why adopt now:

- Semantic retrieval is already in the product, so this is an evolution path.
- Discovery signal supports focused improvements.

### B1. Add first-class capability support

- Add `semantic_retrieval_stack` to `CAPABILITIES`.
- Add structural validator rule in defaults.
- Add capability-specific input/output descriptions in `build_cards()`.

### B2. Improve semantic candidate quality

- Reduce bias from confidence-only preselection in `run_semantic_search()`.
- Use a larger and more balanced candidate set before semantic scoring.
- Keep fallback behavior deterministic when embeddings are unavailable.

### B3. Tune hybrid ranking

- Expose mode weights as constants near `search_cards()`.
- Add one candidate weighting profile focused on semantic-heavy queries.
- Compare against baseline with `compare_reports.py`.

### B4. Add benchmark coverage

- Add 2-3 semantic capability queries to `phase2/benchmark/queries.json`.
- Include expected repos from vector/search-style references.

### B5. Acceptance gate

- Semantic/hybrid mode improves or stays flat on precision and coverage.
- No severe false-positive increase in negative/filter query families.
- Capability cards include auditable evidence paths.

## Workstream C - Adapt `evaluation_harness`

Why adapt (not adopt):

- The concept is valuable, but discovered patterns are broad across many repos.
- We need project-specific gates and reporting semantics before rollout.

### C1. Define project-specific quality contract

- Add explicit quality targets per family (precision, coverage, error budget).
- Define stop/go gates in one config file (for predictable automation).
- Keep taxonomy aligned with `phase2/docs/error_taxonomy.md`.

### C2. Upgrade benchmark outputs for decision-making

- Extend `run_phase2_benchmark.py` report payload with:
  - pass/fail status per mode and family
  - explicit regressions list
  - recommendation hints (`promote`, `iterate`, `reject`)
- Keep backward compatibility for existing report consumers.

### C3. Improve comparison and memo integration

- Extend `compare_reports.py` with gate-aware summary output.
- Feed results into `phase4/integration/decision_memo.md` as a standard section.
- Ensure memo includes options considered and trade-offs by capability.

### C4. Add scenario-focused query packs

- Split queries into packs (core, stress, negatives) to reduce noise.
- Run both core and stress packs before promoting changes.

### C5. Acceptance gate

- Harness produces clear promote/iterate/reject recommendation.
- Decision memo is generated with human-readable and JSON forms.
- Team can review one memo and make a release decision without manual data gathering.

## Sequence and milestones

### Milestone 0 - Baseline lock

- Freeze current baseline report and validator pack.
- Snapshot current decision memo artifacts for before/after comparison.

### Milestone 1 - Workstream A complete

- Implement A1-A4.
- Run phase2 benchmark and verify A5 gate.

### Milestone 2 - Workstream B complete

- Implement B1-B4.
- Run phase2 benchmark and compare against Milestone 1.
- Verify B5 gate.

### Milestone 3 - Workstream C complete

- Implement C1-C4.
- Generate gate-aware benchmark + decision memo.
- Verify C5 gate.

### Milestone 4 - Promote and document

- Promote validator/capability changes that passed gates.
- Record outcomes in `phase2/dogfood/feedback_log.md`.
- Publish final decision memo and final report set.

## Deliverables checklist

- Updated capability schema and validator defaults in `capability_index.py`.
- Updated benchmark queries in `phase2/benchmark/queries.json`.
- Updated benchmark/report scripts in `phase2/scripts/`.
- Updated decision artifacts in `phase4/integration/`:
  - `candidate_capabilities.json`
  - `candidate_validator_pack.json`
  - `candidate_queries.json`
  - `decision_memo.md`
  - `decision_memo.json`

## Risks and mitigations

- Risk: precision drops due to broader capability coverage.
  - Mitigation: enforce per-family no-regression gates before promotion.
- Risk: semantic ranking improvements help one family but harm negatives.
  - Mitigation: always run negative/stress query packs in the same cycle.
- Risk: evaluation harness drifts into generic metrics.
  - Mitigation: keep project-specific quality contract and gate config mandatory.
