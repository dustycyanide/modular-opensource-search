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
