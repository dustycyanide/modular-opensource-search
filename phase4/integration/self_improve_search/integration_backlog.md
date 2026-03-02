# Phase 4 Integration Backlog

Source report: `/Users/dustycyanide/Documents/projects/modular_opensource/phase3/reports/self_improve_search/discovery_report.json`

| Capability | Decision | Reason | High | Medium | High ratio | Expected repos |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `repo_indexing_pipeline` | `adapt` | `broad-signal` | 7 | 0 | 0.538 | chroma, meilisearch, qdrant |
| `semantic_retrieval_stack` | `adapt` | `broad-signal` | 6 | 1 | 0.462 | lancedb, meilisearch, qdrant |
| `structured_filtering` | `adapt` | `broad-signal` | 13 | 0 | 1.0 | ast-grep, chroma, haystack |
| `cli_tooling_surface` | `adapt` | `broad-signal` | 11 | 0 | 0.846 | ast-grep, chroma, haystack |
| `agentic_workflows` | `adapt` | `broad-signal` | 12 | 0 | 0.923 | ast-grep, chroma, haystack |

## Next actions

- Apply `candidate_capabilities.json` entries to `capability_index.py` capability schema.
- Merge `candidate_validator_pack.json` entries into a new phase2 validator pack candidate.
- Append `candidate_queries.json` into benchmark queries for regression checks.
- Run the phase2 benchmark loop and compare against baseline before accepting changes.
