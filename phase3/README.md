# Phase 3 Capability Discovery Lab

Phase 3 extends the process from "evaluate known capabilities" to
"discover candidate capabilities" using targeted OSS cohorts.

## Objective

Run a repeatable discovery pass for capability candidates before touching
`capability_index.py`:

1. Define candidate capabilities with structural signal patterns.
2. Scan indexed repos for evidence of each candidate capability.
3. Rank repo matches by evidence quality.
4. Export discovery report for integration planning (Phase 4).

## Main assets

- `config/candidate_capabilities.json` - discovery capability definitions.
- `scripts/run_phase3_discovery.py` - capability signal scan and scoring.
- `reports/` - generated discovery reports.

## Quick start

```bash
.venv/bin/python phase3/scripts/run_phase3_discovery.py \
  --repos-file phase2/benchmark/repos.json \
  --capabilities-file phase3/config/candidate_capabilities.json \
  --repos-root repos \
  --report phase3/reports/discovery_report.json \
  --max-repos 20
```

## Acceptance gate

Treat a candidate as Phase-4-ready when:

- it has at least 2 `high` quality repo matches, and
- evidence paths are auditable (entrypoints, core modules, tests), and
- at least 1 expected contrast repo does not score `high`.
