# Challenge Card Template

Use one card per quality problem.

## Card

- `id`:
- `title`:
- `query`:
- `family`:
- `mode`: lexical | semantic | hybrid
- `expected_repos`:
- `expected_capabilities`:
- `observed_top_k`:
- `failure_type`: extraction_fp | extraction_fn | ranking_fp | filter_error | mixed
- `severity`: low | medium | high
- `why_it_failed`:
- `candidate_patterns_from_oss`:
- `proposed_validator_change`:
- `risk_of_regression`:
- `success_criteria`:
- `owner`:
- `status`: open | in_progress | validated | closed

## Example

- `id`: CH-API-001
- `title`: API query matches non-API framework
- `query`: python api service
- `family`: api
- `mode`: hybrid
- `expected_repos`: [flask, fastapi]
- `expected_capabilities`: [api_service]
- `observed_top_k`: [click:api_service, flask:api_service]
- `failure_type`: extraction_fp
- `severity`: high
- `why_it_failed`: lexical keyword overlap without route signature proof
- `candidate_patterns_from_oss`: ["@app.route(", "APIRouter(", "router.get("]
- `proposed_validator_change`: require one route signature group + request/response signal
- `risk_of_regression`: medium (may reduce recall for unconventional frameworks)
- `success_criteria`: remove false positive, keep flask/fastapi coverage at >=0.9
- `owner`: unassigned
- `status`: open
