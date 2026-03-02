# Dogfood Feedback Workspace

Use this folder to document how we improve the capability engine by using the
engine itself to discover, evaluate, and integrate open-source capabilities.

## Goal

Create a repeatable dogfood loop:

1. Define capability gaps in this project.
2. Index targeted OSS repo cohorts for those gaps.
3. Search and review evidence-backed matches.
4. Integrate selected patterns into this project.
5. Record what worked, what failed, and what to change next.

## Files

- `capability_backlog.md` - capability definitions and target repo archetypes.
- `repo_seed_sets.md` - recommended indexing cohorts by wave.
- `feedback_log.md` - session-by-session dogfood feedback log.

## Operating rules

- Keep each session scoped to 1-2 capabilities.
- Always include at least one contrast repo to catch false positives.
- Only promote a pattern if it has strong path-level evidence.
- Log both wins and misses; misses drive validator and ranking improvements.

## Hand-off to later phases

- Discovery-ready candidates move to `phase3/` for signal scans across broader cohorts.
- Integration-ready candidates move to `phase4/` for draft capability and validator artifacts.
