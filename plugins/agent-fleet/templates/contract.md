# Change Contract

## Task

```yaml
change_id: <short-slug>
from_task:
  goal: <copy the user's request; do not reinterpret>
  acceptance_criteria: []
  out_of_scope: []
  approvals_required: []
from_research:
  relevant_files: []
  conventions: []
  risks: []
  checks: []
  unverified: []
```

Every research finding needs a repository path or command-output reference. Mark anything not verified as `UNVERIFIED`.

## Blocker Codes

| Code | Meaning |
|---|---|
| `MISSING_CONTEXT` | Research could not find a required dependency or detail. |
| `SCOPE_CREEP` | The diff changes something outside the task. |
| `TEST_FAIL` | A check failed when the reviewer reran it. |
| `CANNOT_VERIFY` | A required check could not be executed. |
| `CRITERIA_UNMET` | An acceptance criterion has no evidence. |
| `SECURITY` | A security or privacy risk blocks approval. |
| `COST` | Unbounded or always-on cost was introduced. |
| `NEEDS_HUMAN` | A decision or action requires human authority. |
| `QUALITY_REGRESSION` | Evaluation regressed beyond the allowed tolerance. |
| `EVAL_INCOMPLETE` | Evaluation data is missing, malformed, or below threshold. |
| `GATE_FAILED` | A required quality gate did not pass. |
| `OTHER` | No code fits; explain why. |

## Completion Report

Write `work/<change-id>/run-report.json` with this shape:

```json
{
  "change_id": "short-slug",
  "commit_sha": "commit-or-working-tree-reference",
  "criteria": [
    {"id": "AC-1", "status": "PASS", "evidence": "tests/test_file.py::test_case"}
  ],
  "checks": [
    {"name": "unit tests", "command": "python -m unittest", "status": "PASS", "reviewer_reran": true}
  ],
  "review": {"verdict": "PASS", "independent": true},
  "unresolved_blockers": [],
  "evaluation": {
    "dataset_version": "1.0.0",
    "cases": [
      {"id": "case-id", "passed": true, "safety_critical": false}
    ]
  }
}
```

Include exactly one scored result for each case in `quality/agent-behavior.jsonl`. Redact secrets and personal data from evidence. The report validator verifies report shape and thresholds; it does not independently verify the truth of submitted outcomes.
