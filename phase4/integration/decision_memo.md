# Capability Decision Memo

Generated: `2026-03-01T23:50:58.679089+00:00`
Source discovery report: `/Users/dustycyanide/Documents/projects/modular_opensource/phase3/reports/discovery_report_16.json`

## Repositories Evaluated

| Repo | Type | Known capabilities | Why it was in scope |
| --- | --- | --- | --- |
| `OCRmyPDF` | OCR application | ocr_processing, document_ingestion_pipeline, cli_tooling | High-signal OCR + pipeline reference and realistic app-level CLI behavior. |
| `requests` | HTTP client library | negative_control, http_client | Contrast repo to catch false positives in API/service-like queries. |
| `flask` | Web framework | api_service | Clear route and request/response signatures for API detection. |
| `click` | CLI framework | cli_tooling | Canonical CLI framework for command signature patterns. |
| `pytesseract` | OCR library | ocr_processing | Library-level OCR reference to complement app-level OCR signals. |
| `fastapi` | API framework | api_service | Strong router/endpoint signatures for API capability grounding. |
| `typer` | CLI framework | cli_tooling | Typed CLI framework to improve CLI recall beyond click-only patterns. |
| `celery` | Task queue framework | async_processing_engine | Reference repo for worker/job/task and queue orchestration signals. |
| `rq` | Queue worker framework | async_processing_engine | Alternative async queue model to prevent overfitting to Celery patterns. |
| `sqlalchemy` | ORM and SQL toolkit | database_persistence | Strong persistence and migration signatures for database capability checks. |
| `django` | Full-stack framework | api_service, database_persistence | Broad framework signals useful for precision stress and contrast. |
| `pydantic` | Data validation library | schema_validation | Useful contrast for data modeling and validation-heavy codebases. |
| `tree-sitter` | Parser infrastructure | code_parsing | Potential source of robust syntax and structure extraction patterns. |
| `ast-grep` | AST search tooling | code_search, pattern_matching | Candidate source for structured code matching and rule-driven search. |
| `zoekt` | Code search engine | repo_indexing_pipeline, search_ranking | High-value reference for large-scale indexing and query retrieval behavior. |
| `chroma` | Vector database | semantic_retrieval_stack, repo_indexing_pipeline | Strong source for embedding retrieval and vector ranking patterns. |

## Repository indexing pipeline (`repo_indexing_pipeline`)

- What this capability is: Repository intake, traversal, metadata extraction, and index write flow.
- Why this is useful here: This project must ingest many repositories reliably, with evidence and metadata quality controls. Better indexing design directly improves retrieval trust.
- Type of repos we looked for: Code search engines and source indexers; Developer tools that crawl repositories; Data systems with explicit ingest and index-write paths
- Discovery outcome: high=4, medium=0, low=10, matched_repos=14
- Repos where we found strongest signal:
  - `celery` (Task queue framework, quality=high, score=0.85): known capabilities [async_processing_engine]
  - `sqlalchemy` (ORM and SQL toolkit, quality=high, score=0.85): known capabilities [database_persistence]
  - `chroma` (Vector database, quality=high, score=0.85): known capabilities [semantic_retrieval_stack, repo_indexing_pipeline]
  - `flask` (Web framework, quality=high, score=0.8): known capabilities [api_service]
- Lower-confidence matches we treated cautiously: OCRmyPDF (low), django (low), tree-sitter (low), zoekt (low)
- Options considered and trade-offs:
  - Adopt now: pros=Fastest path to shipping measurable value; Keeps momentum when evidence is already strong. cons=Risk of overfitting if signal breadth is low; May pull in patterns that are not specific to our domain. Best when: The capability has specific, high-quality matches and clear fit for `repo_indexing_pipeline`
  - Adapt first: pros=Balances speed and safety by tailoring to project constraints; Reduces false positives before capability promotion. cons=Adds design and implementation time; Needs another evaluation loop before final acceptance. Best when: Signal is promising but too broad, noisy, or only partially specific
  - Reject for now: pros=Avoids introducing low-confidence behavior; Protects trust while discovery criteria are refined. cons=Delays potential capability gains; Requires a new repo cohort or sharper detection patterns. Best when: Required signals do not pass consistently or evidence is mostly generic
- Final recommendation: `adopt` (high-signal). Recommend adopt because we have enough high-confidence matches (high=4, medium=0) and the signal is not too broad (high_ratio=0.25).

## Semantic retrieval stack (`semantic_retrieval_stack`)

- What this capability is: Embedding generation, vector similarity search, and retrieval ranking logic.
- Why this is useful here: Capability search quality depends on semantic retrieval and ranking. This capability strengthens query understanding beyond lexical keyword overlap.
- Type of repos we looked for: Vector databases and semantic search systems; Hybrid ranker and retrieval framework repos; Embedding-first developer tools
- Discovery outcome: high=2, medium=0, low=6, matched_repos=8
- Repos where we found strongest signal:
  - `sqlalchemy` (ORM and SQL toolkit, quality=high, score=0.95): known capabilities [database_persistence]
  - `chroma` (Vector database, quality=high, score=0.9): known capabilities [semantic_retrieval_stack, repo_indexing_pipeline]
- Lower-confidence matches we treated cautiously: django (low), zoekt (low), OCRmyPDF (low), pydantic (low)
- Options considered and trade-offs:
  - Adopt now: pros=Fastest path to shipping measurable value; Keeps momentum when evidence is already strong. cons=Risk of overfitting if signal breadth is low; May pull in patterns that are not specific to our domain. Best when: The capability has specific, high-quality matches and clear fit for `semantic_retrieval_stack`
  - Adapt first: pros=Balances speed and safety by tailoring to project constraints; Reduces false positives before capability promotion. cons=Adds design and implementation time; Needs another evaluation loop before final acceptance. Best when: Signal is promising but too broad, noisy, or only partially specific
  - Reject for now: pros=Avoids introducing low-confidence behavior; Protects trust while discovery criteria are refined. cons=Delays potential capability gains; Requires a new repo cohort or sharper detection patterns. Best when: Required signals do not pass consistently or evidence is mostly generic
- Final recommendation: `adopt` (high-signal). Recommend adopt because we have enough high-confidence matches (high=2, medium=0) and the signal is not too broad (high_ratio=0.125).

## Evaluation harness (`evaluation_harness`)

- What this capability is: Benchmark datasets, quality metrics, and report comparison workflows.
- Why this is useful here: Dogfooding requires proving quality changes with objective metrics, not intuition. A strong evaluation harness lets us iterate quickly without silent regressions.
- Type of repos we looked for: Mature repos with benchmark and regression workflows; Projects with quality dashboards and metrics reports; Libraries that compare baseline and candidate performance
- Discovery outcome: high=9, medium=0, low=5, matched_repos=14
- Repos where we found strongest signal:
  - `chroma` (Vector database, quality=high, score=0.9): known capabilities [semantic_retrieval_stack, repo_indexing_pipeline]
  - `pydantic` (Data validation library, quality=high, score=0.85): known capabilities [schema_validation]
  - `zoekt` (Code search engine, quality=high, score=0.85): known capabilities [repo_indexing_pipeline, search_ranking]
  - `OCRmyPDF` (OCR application, quality=high, score=0.8): known capabilities [ocr_processing, document_ingestion_pipeline, cli_tooling]
  - `celery` (Task queue framework, quality=high, score=0.8): known capabilities [async_processing_engine]
  - `rq` (Queue worker framework, quality=high, score=0.8): known capabilities [async_processing_engine]
- Lower-confidence matches we treated cautiously: click (low), typer (low), ast-grep (low), fastapi (low)
- Options considered and trade-offs:
  - Adopt now: pros=Fastest path to shipping measurable value; Keeps momentum when evidence is already strong. cons=Risk of overfitting if signal breadth is medium; May pull in patterns that are not specific to our domain. Best when: The capability has specific, high-quality matches and clear fit for `evaluation_harness`
  - Adapt first: pros=Balances speed and safety by tailoring to project constraints; Reduces false positives before capability promotion. cons=Adds design and implementation time; Needs another evaluation loop before final acceptance. Best when: Signal is promising but too broad, noisy, or only partially specific
  - Reject for now: pros=Avoids introducing low-confidence behavior; Protects trust while discovery criteria are refined. cons=Delays potential capability gains; Requires a new repo cohort or sharper detection patterns. Best when: Required signals do not pass consistently or evidence is mostly generic
- Final recommendation: `adapt` (broad-signal). Recommend adapt because the capability is useful but needs tailoring before rollout (reason=broad-signal, high=9, medium=0, high_ratio=0.562).

## Structured filtering (`structured_filtering`)

- What this capability is: Filter extraction/parsing and metadata-aware result constraints.
- Why this is useful here: Users need dependable filters (language, license, framework) so results can be constrained to practical integration choices.
- Type of repos we looked for: Search platforms with faceted filtering; Metadata-heavy repositories with structured query parsing; Systems with explicit language/license constraints
- Discovery outcome: high=0, medium=0, low=16, matched_repos=16
- Repos where we found strongest signal:
  - No high/medium matches were found.
- Lower-confidence matches we treated cautiously: click (low), sqlalchemy (low), django (low), pydantic (low)
- Options considered and trade-offs:
  - Adopt now: pros=Fastest path to shipping measurable value; Keeps momentum when evidence is already strong. cons=Risk of overfitting if signal breadth is low; May pull in patterns that are not specific to our domain. Best when: The capability has specific, high-quality matches and clear fit for `structured_filtering`
  - Adapt first: pros=Balances speed and safety by tailoring to project constraints; Reduces false positives before capability promotion. cons=Adds design and implementation time; Needs another evaluation loop before final acceptance. Best when: Signal is promising but too broad, noisy, or only partially specific
  - Reject for now: pros=Avoids introducing low-confidence behavior; Protects trust while discovery criteria are refined. cons=Delays potential capability gains; Requires a new repo cohort or sharper detection patterns. Best when: Required signals do not pass consistently or evidence is mostly generic
- Final recommendation: `reject` (weak-signal). Recommend reject for now because confidence is weak or too generic (reason=weak-signal, high=0, medium=0, high_ratio=0.0).

## Final Recommendation Summary

- Adopt: repo_indexing_pipeline, semantic_retrieval_stack
- Adapt: evaluation_harness
- Reject: structured_filtering
