# Phase 4 Capability Integration Planning

Phase 4 converts discovery signals into concrete integration artifacts for
`capability_index.py` and benchmark coverage.

## Objective

1. Read Phase 3 discovery report.
2. Decide `adopt`, `adapt`, or `reject` for each candidate capability.
3. Check recommendation stability against a broader rerun before lock.
4. Generate draft artifacts to speed implementation:
   - candidate capability metadata
   - candidate validator pack entries
   - candidate benchmark queries
   - integration backlog markdown

## Main assets

- `scripts/run_phase4_plan.py` - decision and artifact generator.
- `templates/integration_task_template.md` - checklist template per capability.
- `integration/` - generated planning outputs.

Generated outputs now include a review-friendly decision memo:

- `integration/decision_memo.md` - human-readable capability evaluation memo.
- `integration/decision_memo.json` - structured memo payload for other apps.
- `integration/candidate_decisions.json` now includes `stability_check` and recommendation lock status.

## Quick start

```bash
.venv/bin/python phase4/scripts/run_phase4_plan.py \
  --discovery-report phase3/reports/discovery_report.json \
  --stability-report phase3/reports/discovery_report_broad.json \
  --cohort-manifest phase3/reports/cohort_manifest.json \
  --repo-profiles phase2/benchmark/repo_profiles.json \
  --output-dir phase4/integration
```

## Decision defaults

- `adopt`: at least 2 high-quality matches.
- `adapt`: not adopt, but has enough medium/high signal to iterate safely.
- `reject`: signal too weak or noisy; keep in backlog.
