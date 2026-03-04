# Phase 2 Run Notes

## Baseline run

Command:

```bash
.venv/bin/python phase2/scripts/run_phase2_benchmark.py \
  --repos-file phase2/benchmark/repos.json \
  --queries-file phase2/benchmark/queries.json \
  --validator-pack phase2/validator_packs/baseline_v2.json \
  --report phase2/reports/baseline_report.json \
  --max-repos 5
```

Summary:

- lexical: repo_precision=0.600 repo_coverage=0.417 cap_precision=0.750 errors=1.700
- semantic: repo_precision=0.600 repo_coverage=0.417 cap_precision=0.750 errors=1.700
- hybrid: repo_precision=0.600 repo_coverage=0.417 cap_precision=0.750 errors=1.700

Generated artifacts:

- `phase2/reports/baseline_report.json`
- `phase2/reports/pattern_candidates.json`
- `phase2/challenges/challenge_cards_generated.md`

## Candidate run (CLI recall attempt)

Command:

```bash
.venv/bin/python phase2/scripts/run_phase2_benchmark.py \
  --repos-file phase2/benchmark/repos.json \
  --queries-file phase2/benchmark/queries.json \
  --validator-pack phase2/validator_packs/candidate_cli_recall_v1.json \
  --report phase2/reports/candidate_cli_recall_report.json \
  --max-repos 5
```

Delta vs baseline (`compare_reports.py`):

- Repo coverage improved slightly (+0.033 overall).
- Repo precision dropped slightly (-0.033 overall).
- Errors increased (+0.200 overall).

Decision:

- Candidate pack should not be accepted as-is.
- Keep baseline and iterate with narrower CLI constraints.

## 12-repo baseline expansion

Command:

```bash
.venv/bin/python phase2/scripts/run_phase2_benchmark.py \
  --repos-file phase2/benchmark/repos.json \
  --queries-file phase2/benchmark/queries.json \
  --validator-pack phase2/validator_packs/baseline_v2.json \
  --report phase2/reports/baseline_report_12.json \
  --max-repos 12
```

Summary:

- lexical: repo_precision=0.575 repo_coverage=0.767 cap_precision=0.850 errors=2.100
- semantic: repo_precision=0.595 repo_coverage=0.767 cap_precision=0.850 errors=1.900
- hybrid: repo_precision=0.595 repo_coverage=0.767 cap_precision=0.850 errors=1.900

Compared with 5-repo baseline:

- Coverage improved substantially (+0.350 overall in all modes).
- Capability precision improved (+0.100 overall in all modes).
- Precision dropped slightly for lexical and nearly flat for semantic/hybrid.
- Error counts increased due harder negatives and larger search space.

Generated artifacts:

- `phase2/reports/baseline_report_12.json`
- `phase2/reports/pattern_candidates_12.json`
- `phase2/challenges/challenge_cards_generated_12.md`

## Dogfood Wave 2 expansion (16 repos)

Commands:

```bash
.venv/bin/python phase2/scripts/run_phase2_benchmark.py \
  --repos-file phase2/benchmark/repos.json \
  --queries-file phase2/benchmark/queries.json \
  --validator-pack phase2/validator_packs/baseline_v2.json \
  --report phase2/reports/dogfood_wave2_baseline_12.json \
  --max-repos 12

.venv/bin/python phase2/scripts/run_phase2_benchmark.py \
  --repos-file phase2/benchmark/repos.json \
  --queries-file phase2/benchmark/queries.json \
  --validator-pack phase2/validator_packs/baseline_v2.json \
  --report phase2/reports/dogfood_wave2_candidate_16.json \
  --max-repos 16

.venv/bin/python phase2/scripts/compare_reports.py \
  --baseline phase2/reports/dogfood_wave2_baseline_12.json \
  --candidate phase2/reports/dogfood_wave2_candidate_16.json
```

Added repos (newly cloned):

- `tree-sitter`
- `ast-grep`
- `zoekt`
- `chroma`

Delta vs 12-repo baseline:

- lexical: repo_precision +0.020, errors -0.200
- semantic: unchanged on aggregate metrics
- hybrid: unchanged on aggregate metrics

Decision:

- Keep this Wave 2 subset in benchmark source.
- Expand next to 20 repos only after adding retrieval/indexing-targeted query families.
