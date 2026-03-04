# Phase 4 Integration Backlog

Source report: `/Users/dustycyanide/Documents/projects/modular_opensource/phase3/reports/discovery_report_16.json`

| Capability | Decision | Reason | High | Medium | High ratio | Expected repos |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `repo_indexing_pipeline` | `adopt` | `high-signal` | 4 | 0 | 0.25 | celery, sqlalchemy, chroma |
| `semantic_retrieval_stack` | `adopt` | `high-signal` | 2 | 0 | 0.125 | sqlalchemy, chroma |
| `evaluation_harness` | `adapt` | `broad-signal` | 9 | 0 | 0.562 | chroma, pydantic, zoekt |
| `structured_filtering` | `reject` | `weak-signal` | 0 | 0 | 0.0 | - |

## Next actions

- Apply `candidate_capabilities.json` entries to `capability_index.py` capability schema.
- Merge `candidate_validator_pack.json` entries into a new phase2 validator pack candidate.
- Append `candidate_queries.json` into benchmark queries for regression checks.
- Run the phase2 benchmark loop and compare against baseline before accepting changes.
