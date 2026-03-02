# Capability Backlog (Dogfood)

Define capabilities as concrete, testable outcomes before expanding indexing.

## Current core capabilities

| Capability | Why we need it | Positive repo archetypes | Contrast archetypes |
| --- | --- | --- | --- |
| `document_ingestion_pipeline` | Validate extraction and staged pipeline evidence. | OCR/document ETL tools. | Generic file utilities without pipeline stages. |
| `ocr_processing` | Keep OCR matching high precision with structural proof. | OCR libraries and OCR apps. | Image tooling without text extraction. |
| `async_processing_engine` | Improve worker/queue detection and ranking behavior. | Task queue frameworks and worker apps. | Async syntax-only repos without queues/jobs. |
| `api_service` | Reduce API false positives from keyword overlap. | Web frameworks and API-first services. | HTTP clients and SDK-only repos. |
| `database_persistence` | Improve ORM + SQL evidence confidence. | ORM and migration-heavy repos. | In-memory data structure repos. |
| `cli_tooling` | Recover CLI framework recall without opening API false positives. | CLI frameworks and command apps. | Libraries with no executable entrypoints. |

## Next capability expansions (recommended)

| Capability candidate | Why this matters now | Candidate signals |
| --- | --- | --- |
| `repo_indexing_pipeline` | Ingestion quality is now a key trust bottleneck. | Git clone/update flows, ignore rules, chunking, metadata extraction. |
| `semantic_retrieval_stack` | Ranking quality depends on embeddings + scoring composition. | Embedding model wrappers, vector search, hybrid rankers. |
| `evaluation_harness` | Dogfood loop needs objective quality deltas each run. | Benchmark datasets, precision metrics, report diffing. |
| `structured_filtering` | Users need dependable language/license/framework filtering. | Query parsing, normalized metadata, filter evaluation logic. |

## Definition of done per capability

- At least 2 high-quality positive matches with auditable evidence paths.
- At least 1 contrast repo does not appear in top 5 for target queries.
- One integration note recorded with `adopt`, `adapt`, or `reject` decision.
