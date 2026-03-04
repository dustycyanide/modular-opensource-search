# Dogfood Feedback Log

Use one entry per dogfood session.

---

## Session Template

- Date:
- Owner:
- Capability focus:
- Hypothesis:

### Indexed repos

- Positive set:
- Contrast set:

### Queries used

-

### Results snapshot

- Top matches:
- False positives:
- False negatives:
- Evidence quality notes:

### Integration decision

- Decision: `adopt` | `adapt` | `reject`
- Target area in this project:
- Planned change:
- Risk/trade-off:

### Metrics

- Precision@5:
- Expected-repo coverage:
- Confidence trend vs prior session:

### Follow-ups

-

---

## Session 001

- Date: 2026-03-01
- Owner: OpenCode + Dusty
- Capability focus: `repo_indexing_pipeline`, `evaluation_harness`
- Hypothesis: Expanding from 12 to 16 repos with capability-mining candidates should increase stress coverage without harming current semantic/hybrid quality.

### Indexed repos

- Positive set: Existing 12-repo benchmark set + `tree-sitter`, `ast-grep`, `zoekt`, `chroma`
- Contrast set: Existing contrast remains `requests`; new set acts as broader hard-negative surface

### Queries used

- `phase2/benchmark/queries.json` (all benchmark families)

### Results snapshot

- Top matches: Expected repos remain stable across semantic and hybrid modes.
- False positives: No new semantic/hybrid false-positive spike from added repos.
- False negatives: Unchanged at benchmark aggregate level.
- Evidence quality notes: New repos produced indexable cards without breaking current validator assumptions.

### Integration decision

- Decision: `adopt`
- Target area in this project: `phase2/benchmark/repos.json`
- Planned change: Keep Wave 2 repos in benchmark source and continue incremental max-repo expansion.
- Risk/trade-off: More repos increase ingestion time and can hide regressions without family-level review.

### Metrics

- Precision@5: lexical +0.020 overall; semantic/hybrid unchanged.
- Expected-repo coverage: unchanged overall.
- Confidence trend vs prior session: stable for semantic/hybrid; lexical noise reduced slightly.

### Follow-ups

- Add next Wave 2 batch (`qdrant`, `prefect`, `evidently`, `openevals`) via `--max-repos 20` run.
- Add at least one new query family targeting retrieval/indexing capabilities so new repos are measured directly.
