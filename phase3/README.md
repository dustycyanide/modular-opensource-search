# Phase 3 Capability Discovery Lab

Phase 3 extends the process from "evaluate known capabilities" to
"discover candidate capabilities" using targeted OSS cohorts.

## Objective

Run a repeatable discovery pass for capability candidates before touching
`capability_index.py`:

1. Define candidate capabilities with structural signal patterns.
2. Build a targeted cohort with positive + contrast quotas and diversity gates.
3. Scan selected repos for evidence of each candidate capability.
4. Rank repo matches by evidence quality.
5. Export discovery report for integration planning (Phase 4).

## Main assets

- `config/candidate_capabilities.json` - discovery capability definitions.
- `config/capability_targeting.json` - capability targeting intent and cohort quotas.
- `config/repo_registry.json` - reusable repo registry with tags and quality signals.
- `scripts/build_phase3_cohort.py` - cohort manifest builder and gate checks.
- `scripts/run_phase3_discovery.py` - capability signal scan and scoring.
- `reports/` - generated discovery reports.

## Quick start

```bash
.venv/bin/python phase3/scripts/build_phase3_cohort.py \
  --targeting-spec phase3/config/capability_targeting.json \
  --repo-registry phase3/config/repo_registry.json \
  --output phase3/reports/cohort_manifest.json

.venv/bin/python phase3/scripts/run_phase3_discovery.py \
  --cohort-manifest phase3/reports/cohort_manifest.json \
  --capabilities-file phase3/config/candidate_capabilities.json \
  --repos-root repos \
  --report phase3/reports/discovery_report.json \
  --max-repos 20
```

If selected cohort repos are missing locally, discovery now fails fast by default.
Use `--clone-missing` to hydrate repos or `--allow-weak-cohort` to continue anyway.

## Acceptance gate

Treat a candidate as Phase-4-ready when:

- it has at least 2 `high` quality repo matches, and
- evidence paths are auditable (entrypoints, core modules, tests), and
- at least 1 expected contrast repo does not score `high`, and
- cohort validation gates passed (positives, contrasts, diversity).
