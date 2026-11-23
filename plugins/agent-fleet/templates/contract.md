# Change Artifacts

Each change lives in `work/<change-id>/`. Subagents return one JSON object; the coordinator saves it verbatim. After saving any artifact, run `fleet_state.py update` so its hash is recorded; the validator rejects artifacts edited after that.

## contract.json (researcher)

```json
{
  "change_id": "short-slug",
  "goal": "the user's request, not reinterpreted",
  "acceptance_criteria": [{"id": "AC-1", "text": "testable criterion"}],
  "out_of_scope": [],
  "approvals_required": [],
  "relevant_files": [],
  "conventions": [],
  "risks": [],
  "checks": [{"name": "unit tests", "command": "python -m unittest"}],
  "unverified": []
}
```

Every finding needs a repository path or command-output reference. Mark anything not verified as `UNVERIFIED`. Paths are relative to the repository root.

## implementation.json (implementer)

```json
{
  "change_id": "short-slug",
  "files_changed": [],
  "tests_added": [],
  "commands": [{"command": "python -m unittest", "observed_result": "OK, 12 tests"}],
  "not_run": [],
  "risks": [],
  "blockers": [{"code": "CANNOT_VERIFY", "detail": "why"}]
}
```

## review.json (reviewer)

```json
{
  "change_id": "short-slug",
  "commit_sha": "commit-or-working-tree-reference",
  "verdict": "PASS",
  "independent": true,
  "checks": [
    {"name": "unit tests", "command": "python -m unittest", "status": "PASS", "reviewer_reran": true, "exit_code": 0}
  ],
  "criteria": [
    {"id": "AC-1", "status": "PASS", "evidence": "tests/test_file.py::test_case"}
  ],
  "blockers": []
}
```

Include a check entry for every command in `contract.json` `checks`. `exit_code` is the integer process exit status observed when the reviewer reran the command; it is required on every check. Blocker mapping per check: status `FAIL` maps to `TEST_FAIL` regardless of `exit_code`; status `PASS` (or any other non-`FAIL` status) with a missing, non-integer, boolean, or non-zero `exit_code` maps to `CANNOT_VERIFY`. Use `status` `PASS`, `FAIL`, or `CANNOT_VERIFY`. A FAIL verdict lists blockers with the codes below. Redact secrets and personal data from evidence.

## state.json (fleet_state.py)

Written by `scripts/fleet_state.py`, not by hand: `change_id`, `phase`, `status`, `repair_rounds`, `blocker_history`, and `artifacts` (SHA-256 of each saved artifact).

| Field | Values |
|---|---|
| `phase` | `INTAKE`, `RESEARCH`, `IMPLEMENT`, `REVIEW`, `VALIDATE`, `DONE` |
| `status` | `IN_PROGRESS`, `PASS`, `FAIL`, `PARTIAL` (subagent hit its turn limit), `ERROR` (subagent or tool failure), `TIMEOUT` |

At most two repair rounds are allowed, and the same blockers repeating stops the loop. `fleet_state.py repair` enforces both and exits 3 when a human must decide.

## Blocker Codes

| Code | Meaning |
|---|---|
| `MISSING_CONTEXT` | Research could not find a required dependency or detail. |
| `SCOPE_CREEP` | The diff changes something outside the task. |
| `TEST_FAIL` | A check has status `FAIL` when the reviewer reran it, whatever its `exit_code`. |
| `CANNOT_VERIFY` | A required check could not be executed: status `PASS` (or any non-`FAIL` status) with a missing, non-integer, boolean, or non-zero `exit_code`. |
| `CRITERIA_UNMET` | An acceptance criterion has no evidence. |
| `SECURITY` | A security or privacy risk blocks approval. |
| `COST` | Unbounded or always-on cost was introduced. |
| `NEEDS_HUMAN` | A decision or action requires human authority. |
| `GATE_FAILED` | A required gate did not pass. |
| `OTHER` | No code fits; explain why. |

The behavior-probe suite uses two more codes, `QUALITY_REGRESSION` and `EVAL_INCOMPLETE`; see `quality/README.md`.

The validator checks structure, consistency, and hashes. It does not prove that commands ran or that the reviewer is honest.
