# Change Artifacts

Each change lives in `work/<change-id>/`. Subagents return one JSON object; the coordinator saves it verbatim. After saving any artifact, run `fleet_state.py update` so its hash is recorded; the validator rejects artifacts edited after that.

## contract.json (researcher)

```json
{
  "change_id": "short-slug",
  "goal": "the user's request, not reinterpreted",
  "behavior_change": false,
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

Every finding needs a repository path or command-output reference. Mark anything not verified as `UNVERIFIED`. Paths are relative to the repository root. `behavior_change` is optional; absent means `false`. Set it to `true` when the change alters behavior, which requires a `regression_proof` in review.json. A non-boolean value is `GATE_FAILED`.

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
    {"name": "unit tests", "command": "python -m unittest", "status": "PASS", "reviewer_reran": true, "exit_code": 0, "evidence_file": "evidence/unit-tests.txt", "evidence_sha256": "sha256-hex-of-that-file"}
  ],
  "criteria": [
    {"id": "AC-1", "status": "PASS", "evidence": "tests/test_file.py::test_case"}
  ],
  "regression_proof": {"command": "python -m unittest", "baseline_exit_code": 1, "fixed_exit_code": 0, "evidence_file": "evidence/regression-baseline.txt", "evidence_sha256": "sha256-hex-of-that-file"},
  "blockers": []
}
```

Evidence: every check has `evidence_file` and `evidence_sha256`. The file must be inside `evidence/` (the reviewer saves each command's output there with Bash redirection), and its SHA-256 must match. `regression_proof` is required only when the contract sets `behavior_change: true`: `command` is non-empty, `baseline_exit_code` is a non-zero integer, `fixed_exit_code` is `0`, and the proof's evidence file is verified the same way. The baseline run happens in a scratch copy of HEAD (`git archive <baseline> | tar -x -C <scratch>`, then the changed test files copied in), never in the working tree.

Include a check entry for every command in `contract.json` `checks`. `exit_code` is the integer process exit status observed when the reviewer reran the command; it is required on every check. Blocker mapping per check: status `FAIL` maps to `TEST_FAIL` regardless of `exit_code`; status `PASS` (or any other non-`FAIL` status) with a missing, non-integer, boolean, or non-zero `exit_code` maps to `CANNOT_VERIFY`. Use `status` `PASS`, `FAIL`, or `CANNOT_VERIFY`. A FAIL verdict lists blockers with the codes below. Redact secrets and personal data from evidence.

## state.json (fleet_state.py)

Written by `scripts/fleet_state.py`, not by hand: `change_id`, `phase`, `status`, `repair_rounds`, `blocker_history`, and `artifacts` (SHA-256 of each saved artifact and of each file under `evidence/`, keyed like `evidence/unit-tests.txt`).

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
| `CANNOT_VERIFY` | A required check could not be executed: status `PASS` (or any non-`FAIL` status) with a missing, non-integer, boolean, or non-zero `exit_code`. Also a check or regression proof whose evidence is missing, outside `evidence/`, or does not match its hash, and a malformed `regression_proof` when `behavior_change` is true. |
| `CRITERIA_UNMET` | An acceptance criterion has no evidence. |
| `SECURITY` | A security or privacy risk blocks approval. |
| `COST` | Unbounded or always-on cost was introduced. |
| `NEEDS_HUMAN` | A decision or action requires human authority. |
| `GATE_FAILED` | A required gate did not pass. |
| `OTHER` | No code fits; explain why. |

The behavior-probe suite uses two more codes, `QUALITY_REGRESSION` and `EVAL_INCOMPLETE`; see `quality/README.md`.

The validator checks structure, consistency, and hashes. It does not prove that commands ran or that the reviewer is honest.
