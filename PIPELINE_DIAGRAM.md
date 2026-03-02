# Project Workflow (Simple View)

This is the plain-language flow for how the project works.

```mermaid
flowchart LR
  A[Choose open-source repos to review]
  B[Ingest repos into the tool]
  C[Tool extracts capability cards with evidence]
  D[Search by capability question]
  E[Review ranked matches]
  F[Decide adopt, adapt, or reject]

  A --> B --> C --> D --> E --> F
```

## Continuous Improvement Loop

```mermaid
flowchart LR
  G[Run benchmark queries]
  H[Find misses and false positives]
  I[Discover better patterns from candidate repos]
  J[Generate integration plan]
  K[Update rules and queries]
  L[Re-run and compare results]

  G --> H --> I --> J --> K --> L --> G
```

## What This Means in Practice

- You point the tool at local repositories.
- The tool builds searchable capability summaries with file evidence.
- You search in natural language (for example: "document processing pipeline").
- You get ranked candidates to evaluate quickly.
- The team then decides whether to adopt, adapt, or reject each capability.
- Regular benchmark/discovery cycles improve accuracy over time.
