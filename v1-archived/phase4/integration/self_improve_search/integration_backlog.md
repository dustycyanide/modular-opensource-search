# Phase 4 Integration Backlog

Source report: `/Users/dustycyanide/Documents/projects/modular_opensource/phase3/reports/self_improve_search/discovery_report.json`

| Capability | Evidence tier | Reason | High | Medium | High ratio | Caller-agent decision status | Expected repos |
| --- | --- | --- | ---: | ---: | ---: | --- | --- |
| `repo_indexing_pipeline` | `promising` | `broad-signal` | 7 | 0 | 0.538 | `pending_agent_judgment` | chroma, meilisearch, qdrant |
| `semantic_retrieval_stack` | `promising` | `broad-signal` | 6 | 1 | 0.462 | `pending_agent_judgment` | lancedb, meilisearch, qdrant |
| `structured_filtering` | `promising` | `broad-signal` | 13 | 0 | 1.0 | `pending_agent_judgment` | ast-grep, chroma, haystack |
| `cli_tooling_surface` | `promising` | `broad-signal` | 11 | 0 | 0.846 | `pending_agent_judgment` | ast-grep, chroma, haystack |
| `agentic_workflows` | `promising` | `broad-signal` | 12 | 0 | 0.923 | `pending_agent_judgment` | ast-grep, chroma, haystack |

## Next actions

- Apply `candidate_capabilities.json` entries to `capability_index.py` capability schema.
- Merge `candidate_validator_pack.json` entries into a new phase2 validator pack candidate.
- Append `candidate_queries.json` into benchmark queries for regression checks.
- Run the phase2 benchmark loop and compare against baseline before accepting changes.
