## Project Overview

This project is now v2 of the open-source capability search effort.

The system objective is to orchestrate discovery, ingestion, retrieval,
reranking, and evidence packaging so an AI agent can make adopt/adapt/reject
decisions with traceable proof.

## Current Structure

```text
modular_opensource/
|- v1-archived/
|- docs/
|  `- v2-orchestration-evidence-plan.md
|- src/
|  `- v2/
|- scripts/
|  `- run_v2.py
|- tests/
|- README.md
`- requirements.txt
```

## CLI (v2)

```bash
.venv/bin/python scripts/run_v2.py plan
.venv/bin/python scripts/run_v2.py run --query "<capability-query>" --top-k <k>
.venv/bin/python scripts/run_v2.py run --query "<capability-query>" --local-only --top-k <k>
.venv/bin/python scripts/run_v2.py evaluate --annotations <annotation-csv> --queries <queries-csv>
```

## Working Model

Use v2 contracts in `src/v2/contracts.py` as stable interfaces.
Implement adapters per stage instead of coupling business logic to one search
provider, one embedding model, or one ranking backend.
