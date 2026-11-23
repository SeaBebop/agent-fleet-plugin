#!/usr/bin/env python3
"""Validate the artifacts of one Agent Fleet change against the per-change gate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from fleet_state import ARTIFACTS, EVIDENCE_DIR, MAX_REPAIR_ROUNDS, STATUSES, hash_artifacts

ALLOWED_BLOCKERS = {
    "MISSING_CONTEXT",
    "SCOPE_CREEP",
    "TEST_FAIL",
    "CANNOT_VERIFY",
    "CRITERIA_UNMET",
    "SECURITY",
    "COST",
    "NEEDS_HUMAN",
    "GATE_FAILED",
    "OTHER",
}
VALIDATABLE_PHASES = ("VALIDATE", "DONE")
VALIDATABLE_STATUSES = ("IN_PROGRESS", "PASS")


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _evidence_problem(directory: Path, item: dict[str, Any]) -> str | None:
    """Return why the evidence_file/evidence_sha256 pair does not verify, or None when it does."""
    evidence_file = item.get("evidence_file")
    expected = item.get("evidence_sha256")
    if not _text(evidence_file) or not _text(expected):
        return "evidence_file and evidence_sha256 are required."
    try:
        evidence_root = (directory / EVIDENCE_DIR).resolve()
        target = (directory / evidence_file).resolve()
        if evidence_root not in target.parents:
            return f"evidence_file must be inside {EVIDENCE_DIR}/ of the change directory."
        if not target.is_file():
            return f"evidence file {evidence_file} is missing."
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
    except (OSError, ValueError):
        return f"evidence file {evidence_file} cannot be read."
    if actual != expected:
        return f"evidence file {evidence_file} does not match evidence_sha256."
    return None


def _regression_proof_problem(directory: Path, proof: Any) -> str | None:
    if not isinstance(proof, dict):
        return "regression_proof must be an object."
    if not _text(proof.get("command")):
        return "regression_proof needs a non-empty command."
    baseline = proof.get("baseline_exit_code")
    if type(baseline) is not int or baseline == 0:
        return "regression_proof baseline_exit_code must be a non-zero integer."
    fixed = proof.get("fixed_exit_code")
    if type(fixed) is not int or fixed != 0:
        return "regression_proof fixed_exit_code must be the integer 0."
    return _evidence_problem(directory, proof)


def validate_change(directory: Path) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []

    def block(code: str, detail: str) -> None:
        blockers.append({"code": code, "detail": detail})

    def load(name: str) -> Any:
        path = directory / name
        if not path.is_file():
            block("GATE_FAILED", f"{name} is missing.")
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except ValueError as error:
            block("GATE_FAILED", f"{name} is not valid JSON: {error}")
            return None

    if not directory.is_dir():
        block("GATE_FAILED", f"{directory} is not a directory.")
        return {"verdict": "FAIL", "blockers": blockers}

    state = load("state.json")
    contract = load("contract.json")
    implementation = load("implementation.json")
    review = load("review.json")
    if not (directory / "task.md").is_file():
        block("GATE_FAILED", "task.md is missing.")

    change_id = None
    if isinstance(state, dict):
        change_id = state.get("change_id")
        if not _text(change_id):
            block("GATE_FAILED", "state.json must include change_id.")
        if state.get("phase") not in VALIDATABLE_PHASES:
            block("GATE_FAILED", f"state.json phase must be one of {', '.join(VALIDATABLE_PHASES)} before validation.")
        status = state.get("status")
        if status not in STATUSES:
            block("GATE_FAILED", "state.json has an unknown status.")
        elif status not in VALIDATABLE_STATUSES:
            block("GATE_FAILED", f"Run status is {status}; a human decision is required.")
        rounds = state.get("repair_rounds")
        if type(rounds) is not int or not 0 <= rounds <= MAX_REPAIR_ROUNDS:
            block("GATE_FAILED", f"repair_rounds must be an integer from 0 to {MAX_REPAIR_ROUNDS}.")
        recorded = state.get("artifacts")
        if not isinstance(recorded, dict):
            block("GATE_FAILED", "state.json must include artifact hashes.")
        else:
            for name, actual in hash_artifacts(directory).items():
                if recorded.get(name) != actual:
                    block("GATE_FAILED", f"{name} changed after the last state update; run fleet_state.py update.")
    elif state is not None:
        block("GATE_FAILED", "state.json must be a JSON object.")

    criteria_ids: list[str] = []
    contract_commands: list[str] = []
    behavior_change = False
    if isinstance(contract, dict):
        if contract.get("change_id") != change_id:
            block("GATE_FAILED", "contract.json change_id does not match state.json.")
        declared = contract.get("behavior_change", False)
        if type(declared) is bool:
            behavior_change = declared
        else:
            block("GATE_FAILED", "contract.json behavior_change must be true or false when present.")
        criteria = contract.get("acceptance_criteria")
        if (
            not isinstance(criteria, list)
            or not criteria
            or not all(isinstance(item, dict) and _text(item.get("id")) and _text(item.get("text")) for item in criteria)
        ):
            block("CRITERIA_UNMET", "contract.json needs acceptance criteria with an id and text each.")
        else:
            criteria_ids = [item["id"] for item in criteria]
            if len(criteria_ids) != len(set(criteria_ids)):
                block("CRITERIA_UNMET", "Acceptance criterion IDs must be unique.")
        checks = contract.get("checks")
        if isinstance(checks, list):
            contract_commands = [item["command"] for item in checks if isinstance(item, dict) and _text(item.get("command"))]
    elif contract is not None:
        block("GATE_FAILED", "contract.json must be a JSON object.")

    if isinstance(implementation, dict):
        if implementation.get("change_id") != change_id:
            block("GATE_FAILED", "implementation.json change_id does not match state.json.")
    elif implementation is not None:
        block("GATE_FAILED", "implementation.json must be a JSON object.")

    if isinstance(review, dict):
        if review.get("change_id") != change_id:
            block("GATE_FAILED", "review.json change_id does not match state.json.")
        if not _text(review.get("commit_sha")):
            block("GATE_FAILED", "review.json must include commit_sha for traceability.")
        if review.get("verdict") != "PASS" or review.get("independent") is not True:
            block("GATE_FAILED", "An independent reviewer PASS is required.")

        reviewed = review.get("criteria")
        by_id = {item.get("id"): item for item in reviewed if isinstance(item, dict)} if isinstance(reviewed, list) else {}
        for criterion_id in criteria_ids:
            item = by_id.get(criterion_id)
            if item is None or item.get("status") != "PASS" or not _text(item.get("evidence")):
                block("CRITERIA_UNMET", f"Criterion {criterion_id} needs a PASS with evidence in review.json.")

        checks = review.get("checks")
        if not isinstance(checks, list) or not checks:
            block("CANNOT_VERIFY", "At least one independently rerun check is required.")
        else:
            for check in checks:
                exit_ok = isinstance(check, dict) and type(check.get("exit_code")) is int and check.get("exit_code") == 0
                if (
                    not isinstance(check, dict)
                    or not _text(check.get("name"))
                    or not _text(check.get("command"))
                    or not exit_ok
                    or check.get("status") != "PASS"
                    or check.get("reviewer_reran") is not True
                ):
                    code = "TEST_FAIL" if isinstance(check, dict) and check.get("status") == "FAIL" else "CANNOT_VERIFY"
                    block(code, "Every check needs a name, command, integer exit_code of 0, PASS result, and reviewer rerun.")
                    break
            for check in checks:
                problem = _evidence_problem(directory, check) if isinstance(check, dict) else None
                if problem:
                    block("CANNOT_VERIFY", f"Check evidence rejected: {problem}")
                    break
            rerun = {check.get("command") for check in checks if isinstance(check, dict) and check.get("reviewer_reran") is True}
            for command in contract_commands:
                if command not in rerun:
                    block("CANNOT_VERIFY", f"Contract check was not rerun by the reviewer: {command}")

        if behavior_change:
            problem = _regression_proof_problem(directory, review.get("regression_proof"))
            if problem:
                block("CANNOT_VERIFY", f"Behavior change needs a valid regression_proof: {problem}")

        unresolved = review.get("blockers")
        if not isinstance(unresolved, list):
            block("GATE_FAILED", "review.json blockers must be a list.")
        else:
            for item in unresolved:
                if not isinstance(item, dict) or item.get("code") not in ALLOWED_BLOCKERS:
                    block("GATE_FAILED", "A reviewer blocker has an unknown or missing code.")
                    break
            if unresolved:
                block("GATE_FAILED", "Unresolved blockers remain.")
    elif review is not None:
        block("GATE_FAILED", "review.json must be a JSON object.")

    result: dict[str, Any] = {"verdict": "PASS" if not blockers else "FAIL", "blockers": blockers}
    if isinstance(state, dict) and isinstance(state.get("repair_rounds"), int):
        result["metrics"] = {
            "repair_rounds": state["repair_rounds"],
            "criteria_total": len(criteria_ids),
            "artifacts_hashed": len(hash_artifacts(directory)),
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("change_dir", type=Path, help=f"change directory holding {', '.join(ARTIFACTS)} and state.json")
    args = parser.parse_args()

    result = validate_change(args.change_dir)
    print(json.dumps(result, indent=2))
    if not args.change_dir.is_dir():
        return 2
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
