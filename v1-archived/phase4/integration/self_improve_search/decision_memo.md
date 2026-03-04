# Capability Decision Memo

Generated: `2026-03-02T01:18:59.648792+00:00`
Source discovery report: `/Users/dustycyanide/Documents/projects/modular_opensource/phase3/reports/self_improve_search/discovery_report.json`

## Repo Types Sought

| Capability | Repo types sought | Contrast repo types |
| --- | --- | --- |
| `repo_indexing_pipeline` | Search/index infrastructure repositories | - |
| `semantic_retrieval_stack` | Vector and retrieval repositories | - |
| `structured_filtering` | Search and AST parsing repositories | - |
| `cli_tooling_surface` | Search infrastructure with operator-facing CLIs | - |
| `agentic_workflows` | Agentic retrieval frameworks | - |

## Repositories Evaluated

| Repo | Type | Known capabilities | Why it was in scope |
| --- | --- | --- | --- |
| `ast-grep` | AST search tooling | code_search, pattern_matching | Candidate source for structured code matching and rule-driven search. |
| `chroma` | Vector database | semantic_retrieval_stack, repo_indexing_pipeline | Strong source for embedding retrieval and vector ranking patterns. |
| `click` | CLI framework | cli_tooling | Canonical CLI framework for command signature patterns. |
| `haystack` | Unknown | - | No profile summary available. |
| `lancedb` | Unknown | - | No profile summary available. |
| `meilisearch` | Unknown | - | No profile summary available. |
| `pydantic` | Data validation library | schema_validation | Useful contrast for data modeling and validation-heavy codebases. |
| `qdrant` | Vector database | semantic_retrieval_stack | Secondary vector-system reference for ANN and retrieval architecture patterns. |
| `quickwit` | Unknown | - | No profile summary available. |
| `requests` | HTTP client library | negative_control, http_client | Contrast repo to catch false positives in API/service-like queries. |
| `tantivy` | Unknown | - | No profile summary available. |
| `tree-sitter` | Parser infrastructure | code_parsing | Potential source of robust syntax and structure extraction patterns. |
| `zoekt` | Code search engine | repo_indexing_pipeline, search_ranking | High-value reference for large-scale indexing and query retrieval behavior. |

## Capabilities Observed

- `ast-grep`: structured_filtering (high, score=1.0); agentic_workflows (high, score=1.0); cli_tooling_surface (high, score=0.95); repo_indexing_pipeline (low, score=0.6); semantic_retrieval_stack (low, score=0.45)
- `chroma`: repo_indexing_pipeline (high, score=1.0); structured_filtering (high, score=1.0); agentic_workflows (high, score=1.0); semantic_retrieval_stack (high, score=0.95); cli_tooling_surface (high, score=0.95)
- `click`: structured_filtering (high, score=0.95); cli_tooling_surface (high, score=0.9); agentic_workflows (low, score=0.65)
- `haystack`: structured_filtering (high, score=1.0); agentic_workflows (high, score=1.0); cli_tooling_surface (high, score=0.95); semantic_retrieval_stack (medium, score=0.85); repo_indexing_pipeline (low, score=0.65)
- `lancedb`: semantic_retrieval_stack (high, score=1.0); structured_filtering (high, score=1.0); agentic_workflows (high, score=1.0); repo_indexing_pipeline (high, score=0.95); cli_tooling_surface (high, score=0.95)
- `meilisearch`: repo_indexing_pipeline (high, score=1.0); semantic_retrieval_stack (high, score=1.0); agentic_workflows (high, score=1.0); structured_filtering (high, score=0.95); cli_tooling_surface (high, score=0.95)
- `pydantic`: structured_filtering (high, score=1.0); cli_tooling_surface (high, score=0.95); agentic_workflows (high, score=0.95); repo_indexing_pipeline (low, score=0.65); semantic_retrieval_stack (low, score=0.55)
- `qdrant`: repo_indexing_pipeline (high, score=1.0); semantic_retrieval_stack (high, score=1.0); structured_filtering (high, score=1.0); agentic_workflows (high, score=1.0); cli_tooling_surface (high, score=0.9)
- `quickwit`: repo_indexing_pipeline (high, score=1.0); structured_filtering (high, score=1.0); agentic_workflows (high, score=1.0); cli_tooling_surface (high, score=0.95); semantic_retrieval_stack (high, score=0.9)
- `requests`: agentic_workflows (high, score=0.95); structured_filtering (high, score=0.85); cli_tooling_surface (low, score=0.6); repo_indexing_pipeline (low, score=0.517)
- `tantivy`: repo_indexing_pipeline (high, score=1.0); structured_filtering (high, score=1.0); agentic_workflows (high, score=0.95); semantic_retrieval_stack (high, score=0.9); cli_tooling_surface (low, score=0.65)
- `tree-sitter`: structured_filtering (high, score=1.0); agentic_workflows (high, score=1.0); cli_tooling_surface (high, score=0.9); repo_indexing_pipeline (low, score=0.6); semantic_retrieval_stack (low, score=0.55)
- `zoekt`: repo_indexing_pipeline (high, score=1.0); structured_filtering (high, score=0.95); cli_tooling_surface (high, score=0.9); agentic_workflows (high, score=0.9); semantic_retrieval_stack (low, score=0.6)

## Repository indexing pipeline (`repo_indexing_pipeline`)

- What this capability is: Repo traversal, document extraction, and index-write flow for search.
- Why this is useful here: High-quality indexing controls both retrieval quality and evidence trust for capability cards.
- Type of repos we looked for: Search/index infrastructure repositories
- Discovery outcome: high=7, medium=0, low=5, matched_repos=12
- Repos where we found strongest signal:
  - `chroma` (Vector database, quality=high, score=1.0): known capabilities [semantic_retrieval_stack, repo_indexing_pipeline]
  - `meilisearch` (Unknown, quality=high, score=1.0): known capabilities [unknown]
  - `qdrant` (Vector database, quality=high, score=1.0): known capabilities [semantic_retrieval_stack]
  - `quickwit` (Unknown, quality=high, score=1.0): known capabilities [unknown]
  - `tantivy` (Unknown, quality=high, score=1.0): known capabilities [unknown]
  - `zoekt` (Code search engine, quality=high, score=1.0): known capabilities [repo_indexing_pipeline, search_ranking]
- Lower-confidence matches we treated cautiously: haystack (low), pydantic (low), ast-grep (low), tree-sitter (low)
- Options considered and trade-offs:
  - Adopt now: pros=Fastest path to shipping measurable value; Keeps momentum when evidence is already strong. cons=Risk of overfitting if signal breadth is medium; May pull in patterns that are not specific to our domain. Best when: The capability has specific, high-quality matches and clear fit for `repo_indexing_pipeline`
  - Adapt first: pros=Balances speed and safety by tailoring to project constraints; Reduces false positives before capability promotion. cons=Adds design and implementation time; Needs another evaluation loop before final acceptance. Best when: Signal is promising but too broad, noisy, or only partially specific
  - Reject for now: pros=Avoids introducing low-confidence behavior; Protects trust while discovery criteria are refined. cons=Delays potential capability gains; Requires a new repo cohort or sharper detection patterns. Best when: Required signals do not pass consistently or evidence is mostly generic
- Evidence tier: `promising` (broad-signal). Evidence summary: tier=promising, reason=broad-signal, high=7, medium=0, high_ratio=0.538. Final adopt/adapt judgment is intentionally deferred to the calling agent.
- Final decision ownership: owner=`caller_agent`, status=`pending_agent_judgment`, decision=`None`
- Evidence stability: stable across compared runs.

## Semantic retrieval stack (`semantic_retrieval_stack`)

- What this capability is: Embeddings, vector similarity retrieval, and ranking logic.
- Why this is useful here: Semantic retrieval is the core upgrade path for better capability matching versus lexical-only search.
- Type of repos we looked for: Vector and retrieval repositories
- Discovery outcome: high=6, medium=1, low=4, matched_repos=11
- Repos where we found strongest signal:
  - `lancedb` (Unknown, quality=high, score=1.0): known capabilities [unknown]
  - `meilisearch` (Unknown, quality=high, score=1.0): known capabilities [unknown]
  - `qdrant` (Vector database, quality=high, score=1.0): known capabilities [semantic_retrieval_stack]
  - `chroma` (Vector database, quality=high, score=0.95): known capabilities [semantic_retrieval_stack, repo_indexing_pipeline]
  - `quickwit` (Unknown, quality=high, score=0.9): known capabilities [unknown]
  - `tantivy` (Unknown, quality=high, score=0.9): known capabilities [unknown]
- Lower-confidence matches we treated cautiously: zoekt (low), pydantic (low), tree-sitter (low), ast-grep (low)
- Options considered and trade-offs:
  - Adopt now: pros=Fastest path to shipping measurable value; Keeps momentum when evidence is already strong. cons=Risk of overfitting if signal breadth is medium; May pull in patterns that are not specific to our domain. Best when: The capability has specific, high-quality matches and clear fit for `semantic_retrieval_stack`
  - Adapt first: pros=Balances speed and safety by tailoring to project constraints; Reduces false positives before capability promotion. cons=Adds design and implementation time; Needs another evaluation loop before final acceptance. Best when: Signal is promising but too broad, noisy, or only partially specific
  - Reject for now: pros=Avoids introducing low-confidence behavior; Protects trust while discovery criteria are refined. cons=Delays potential capability gains; Requires a new repo cohort or sharper detection patterns. Best when: Required signals do not pass consistently or evidence is mostly generic
- Evidence tier: `promising` (broad-signal). Evidence summary: tier=promising, reason=broad-signal, high=6, medium=1, high_ratio=0.462. Final adopt/adapt judgment is intentionally deferred to the calling agent.
- Final decision ownership: owner=`caller_agent`, status=`pending_agent_judgment`, decision=`None`
- Evidence stability: stable across compared runs.

## Structured filtering and query parsing (`structured_filtering`)

- What this capability is: Query parsing plus metadata or field-level filtering for constrained results.
- Why this is useful here: Capability search needs reliable constraints (language, license, framework) to keep candidate sets actionable.
- Type of repos we looked for: Search and AST parsing repositories
- Discovery outcome: high=13, medium=0, low=0, matched_repos=13
- Repos where we found strongest signal:
  - `ast-grep` (AST search tooling, quality=high, score=1.0): known capabilities [code_search, pattern_matching]
  - `chroma` (Vector database, quality=high, score=1.0): known capabilities [semantic_retrieval_stack, repo_indexing_pipeline]
  - `haystack` (Unknown, quality=high, score=1.0): known capabilities [unknown]
  - `lancedb` (Unknown, quality=high, score=1.0): known capabilities [unknown]
  - `pydantic` (Data validation library, quality=high, score=1.0): known capabilities [schema_validation]
  - `qdrant` (Vector database, quality=high, score=1.0): known capabilities [semantic_retrieval_stack]
- Options considered and trade-offs:
  - Adopt now: pros=Fastest path to shipping measurable value; Keeps momentum when evidence is already strong. cons=Risk of overfitting if signal breadth is medium; May pull in patterns that are not specific to our domain. Best when: The capability has specific, high-quality matches and clear fit for `structured_filtering`
  - Adapt first: pros=Balances speed and safety by tailoring to project constraints; Reduces false positives before capability promotion. cons=Adds design and implementation time; Needs another evaluation loop before final acceptance. Best when: Signal is promising but too broad, noisy, or only partially specific
  - Reject for now: pros=Avoids introducing low-confidence behavior; Protects trust while discovery criteria are refined. cons=Delays potential capability gains; Requires a new repo cohort or sharper detection patterns. Best when: Required signals do not pass consistently or evidence is mostly generic
- Evidence tier: `promising` (broad-signal). Evidence summary: tier=promising, reason=broad-signal, high=13, medium=0, high_ratio=1.0. Final adopt/adapt judgment is intentionally deferred to the calling agent.
- Final decision ownership: owner=`caller_agent`, status=`pending_agent_judgment`, decision=`None`
- Evidence stability: stable across compared runs.

## Tool-use CLI surface (`cli_tooling_surface`)

- What this capability is: Command-line interfaces that expose ingest/search/eval workflows through explicit commands.
- Why this is useful here: A clear CLI surface makes this project easier to automate in agent loops and benchmark workflows.
- Type of repos we looked for: Search infrastructure with operator-facing CLIs
- Discovery outcome: high=11, medium=0, low=2, matched_repos=13
- Repos where we found strongest signal:
  - `ast-grep` (AST search tooling, quality=high, score=0.95): known capabilities [code_search, pattern_matching]
  - `chroma` (Vector database, quality=high, score=0.95): known capabilities [semantic_retrieval_stack, repo_indexing_pipeline]
  - `haystack` (Unknown, quality=high, score=0.95): known capabilities [unknown]
  - `lancedb` (Unknown, quality=high, score=0.95): known capabilities [unknown]
  - `meilisearch` (Unknown, quality=high, score=0.95): known capabilities [unknown]
  - `pydantic` (Data validation library, quality=high, score=0.95): known capabilities [schema_validation]
- Lower-confidence matches we treated cautiously: tantivy (low), requests (low)
- Options considered and trade-offs:
  - Adopt now: pros=Fastest path to shipping measurable value; Keeps momentum when evidence is already strong. cons=Risk of overfitting if signal breadth is medium; May pull in patterns that are not specific to our domain. Best when: The capability has specific, high-quality matches and clear fit for `cli_tooling_surface`
  - Adapt first: pros=Balances speed and safety by tailoring to project constraints; Reduces false positives before capability promotion. cons=Adds design and implementation time; Needs another evaluation loop before final acceptance. Best when: Signal is promising but too broad, noisy, or only partially specific
  - Reject for now: pros=Avoids introducing low-confidence behavior; Protects trust while discovery criteria are refined. cons=Delays potential capability gains; Requires a new repo cohort or sharper detection patterns. Best when: Required signals do not pass consistently or evidence is mostly generic
- Evidence tier: `promising` (broad-signal). Evidence summary: tier=promising, reason=broad-signal, high=11, medium=0, high_ratio=0.846. Final adopt/adapt judgment is intentionally deferred to the calling agent.
- Final decision ownership: owner=`caller_agent`, status=`pending_agent_judgment`, decision=`None`
- Evidence stability: stable across compared runs.

## Agent and workflow orchestration (`agentic_workflows`)

- What this capability is: Patterns for planner/executor style loops and tool-orchestrated retrieval workflows.
- Why this is useful here: Agentic orchestration is needed to run iterative discovery and synthesis loops over capability evidence.
- Type of repos we looked for: Agentic retrieval frameworks
- Discovery outcome: high=12, medium=0, low=1, matched_repos=13
- Repos where we found strongest signal:
  - `ast-grep` (AST search tooling, quality=high, score=1.0): known capabilities [code_search, pattern_matching]
  - `chroma` (Vector database, quality=high, score=1.0): known capabilities [semantic_retrieval_stack, repo_indexing_pipeline]
  - `haystack` (Unknown, quality=high, score=1.0): known capabilities [unknown]
  - `lancedb` (Unknown, quality=high, score=1.0): known capabilities [unknown]
  - `meilisearch` (Unknown, quality=high, score=1.0): known capabilities [unknown]
  - `qdrant` (Vector database, quality=high, score=1.0): known capabilities [semantic_retrieval_stack]
- Lower-confidence matches we treated cautiously: click (low)
- Options considered and trade-offs:
  - Adopt now: pros=Fastest path to shipping measurable value; Keeps momentum when evidence is already strong. cons=Risk of overfitting if signal breadth is medium; May pull in patterns that are not specific to our domain. Best when: The capability has specific, high-quality matches and clear fit for `agentic_workflows`
  - Adapt first: pros=Balances speed and safety by tailoring to project constraints; Reduces false positives before capability promotion. cons=Adds design and implementation time; Needs another evaluation loop before final acceptance. Best when: Signal is promising but too broad, noisy, or only partially specific
  - Reject for now: pros=Avoids introducing low-confidence behavior; Protects trust while discovery criteria are refined. cons=Delays potential capability gains; Requires a new repo cohort or sharper detection patterns. Best when: Required signals do not pass consistently or evidence is mostly generic
- Evidence tier: `promising` (broad-signal). Evidence summary: tier=promising, reason=broad-signal, high=12, medium=0, high_ratio=0.923. Final adopt/adapt judgment is intentionally deferred to the calling agent.
- Final decision ownership: owner=`caller_agent`, status=`pending_agent_judgment`, decision=`None`
- Evidence stability: stable across compared runs.

## Final Decision Ownership

- Final decision owner: `caller_agent`
- Final decision status: `pending_agent_judgment`
- Stability status: `stable`
- Stability compared report: `/Users/dustycyanide/Documents/projects/modular_opensource/phase3/reports/self_improve_search/discovery_report_rerun.json`
- Stability agreement ratio: 1.0
- Pending capabilities for caller-agent judgment: repo_indexing_pipeline, semantic_retrieval_stack, structured_filtering, cli_tooling_surface, agentic_workflows
