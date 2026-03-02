# Phase 2 Process Lab

This phase is for process acceleration, not product formalization.

## Objective

Improve retrieval quality through a repeatable loop:

1. Run benchmark.
2. Classify errors.
3. Mine open-source patterns for failing cases.
4. Update validator pack.
5. Re-run and compare deltas.

## Main assets

- `benchmark/repos.json` - candidate OSS repositories.
- `benchmark/repo_profiles.json` - repo type/capability context for review memos.
- `benchmark/queries.json` - query benchmark set with expected outcomes.
- `validator_packs/` - pluggable structural validator packs.
- `challenges/challenge_cards.md` - human-readable failure backlog.
- `dogfood/` - capability backlog, seed cohorts, and session feedback logs.
- `scripts/run_phase2_benchmark.py` - ingestion + benchmark runner.
- `scripts/mine_patterns.py` - pattern mining from benchmark errors.
- `scripts/compare_reports.py` - report delta summary.
- `scripts/generate_challenge_cards.py` - challenge card generation.

## Recommended iteration loop

```bash
# 1) run benchmark
.venv/bin/python phase2/scripts/run_phase2_benchmark.py \
  --repos-file phase2/benchmark/repos.json \
  --queries-file phase2/benchmark/queries.json \
  --validator-pack phase2/validator_packs/baseline_v2.json \
  --report phase2/reports/baseline_report.json

# 2) mine patterns from errors
.venv/bin/python phase2/scripts/mine_patterns.py \
  --report phase2/reports/baseline_report.json \
  --repos-root repos \
  --output phase2/reports/pattern_candidates.json

# 3) generate challenge cards
.venv/bin/python phase2/scripts/generate_challenge_cards.py \
  --report phase2/reports/baseline_report.json \
  --output phase2/challenges/challenge_cards_generated.md

# 4) edit validator pack, rerun benchmark, and compare
.venv/bin/python phase2/scripts/run_phase2_benchmark.py \
  --repos-file phase2/benchmark/repos.json \
  --queries-file phase2/benchmark/queries.json \
  --validator-pack phase2/validator_packs/baseline_v2.json \
  --report phase2/reports/candidate_report.json

.venv/bin/python phase2/scripts/compare_reports.py \
  --baseline phase2/reports/baseline_report.json \
  --candidate phase2/reports/candidate_report.json
```

## Decision gates

- Accept validator/ranker change only if:
  - repo precision does not regress > 0.05 on any family
  - at least one target family improves
  - no new severe false-positive spike
