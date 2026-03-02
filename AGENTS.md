## Project Overview
This project is a search engine over open-source repositories for specific capabilities. For example, if we want to search for a document processing pipeline over all open-source repositories, we would:
1. First identify repositories that may or might contain document processing engines.
2. Ingest those repos, index them, search across them, identify any matches, then decide if we are going to adopt, adapt, or reject that capability.
3. The final result will be a single document that summarizes what was searched, provides the options and recommendations, and captures the trade-offs that were considered acceptable.

## Directory Structure
```text
modular_opensource/
|- capability_index.py
|- data/
|- repos/
|- thoughts/
|- README.md
|- requirements.txt
|- iterative_repos_test.py
`- iterative_modes_test.py
```

## Feature Workflow
Feature workflow is done in `thoughts/features/`, which is a sim linked directory. Folder names use Linear ticket numbers (for example, `thoughts/features/M-123/`, `thoughts/features/O-456/`, and `thoughts/features/S-789/`), and we track everything in Linear.

## How To Call The Tool
Use placeholder-style commands so agents can reuse the same invocation pattern in any environment.

```bash
# Core search workflow
.venv/bin/python capability_index.py init --db <db-path>
.venv/bin/python capability_index.py ingest --repo <local-repo-path> --db <db-path>
.venv/bin/python capability_index.py search -q "<capability-query>" --top <k> --db <db-path>

# Response detail
.venv/bin/python capability_index.py search -q "<capability-query>" --db <db-path> --response final
.venv/bin/python capability_index.py search -q "<capability-query>" --db <db-path> --response verbose

# Help and command discovery
.venv/bin/python capability_index.py help
.venv/bin/python capability_index.py help <command>

# Cohort-first discovery pipeline
.venv/bin/python phase3/scripts/build_phase3_cohort.py \
  --targeting-spec <targeting-spec-json> \
  --repo-registry <repo-registry-json> \
  --output <cohort-manifest-json>

.venv/bin/python phase3/scripts/run_phase3_discovery.py \
  --cohort-manifest <cohort-manifest-json> \
  --capabilities-file <candidate-capabilities-json> \
  --report <discovery-report-json>

.venv/bin/python phase4/scripts/run_phase4_plan.py \
  --discovery-report <discovery-report-json> \
  --stability-report <discovery-report-rerun-json> \
  --cohort-manifest <cohort-manifest-json> \
  --output-dir <phase4-output-dir>
```
