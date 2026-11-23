#!/usr/bin/env python3
"""Create and update the state file for an Agent Fleet change directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ARTIFACTS = ("task.md", "contract.json", "implementation.json", "review.json")
PHASES = ("INTAKE", "RESEARCH", "IMPLEMENT", "REVIEW", "VALIDATE", "DONE")
STATUSES = ("IN_PROGRESS", "PASS", "FAIL", "PARTIAL", "ERROR", "TIMEOUT")
MAX_REPAIR_ROUNDS = 2
CHANGE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
STATE_FILE = "state.json"


def hash_artifacts(directory: Path) -> dict[str, str]:
    return {
        name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
        for name in ARTIFACTS
        if (directory / name).is_file()
    }


def read_state(directory: Path) -> dict[str, Any]:
    return json.loads((directory / STATE_FILE).read_text(encoding="utf-8"))


def write_state(directory: Path, state: dict[str, Any]) -> None:
    state["artifacts"] = hash_artifacts(directory)
    (directory / STATE_FILE).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def init_state(directory: Path, change_id: str) -> dict[str, Any]:
    if not CHANGE_ID.match(change_id):
        raise ValueError("change id must be lowercase letters, digits, and hyphens (max 64 characters)")
    if (directory / STATE_FILE).exists():
        raise ValueError(f"{directory / STATE_FILE} already exists")
    directory.mkdir(parents=True, exist_ok=True)
    state: dict[str, Any] = {
        "schema_version": 1,
        "change_id": change_id,
        "phase": "INTAKE",
        "status": "IN_PROGRESS",
        "repair_rounds": 0,
        "blocker_history": [],
        "artifacts": {},
    }
    write_state(directory, state)
    return state


def update_state(directory: Path, phase: str | None, status: str | None) -> dict[str, Any]:
    state = read_state(directory)
    if phase is not None:
        if phase not in PHASES:
            raise ValueError(f"phase must be one of {', '.join(PHASES)}")
        state["phase"] = phase
    if status is not None:
        if status not in STATUSES:
            raise ValueError(f"status must be one of {', '.join(STATUSES)}")
        state["status"] = status
    write_state(directory, state)
    return state


def record_repair(directory: Path, codes: list[str]) -> tuple[dict[str, Any], str | None]:
    """Count a repair round; return a stop reason when the loop must end for a human decision."""
    state = read_state(directory)
    codes = sorted(set(codes))
    history = state.setdefault("blocker_history", [])
    reason = None
    if history and history[-1] == codes:
        reason = f"Blockers repeated unchanged: {', '.join(codes)}"
    elif state.get("repair_rounds", 0) >= MAX_REPAIR_ROUNDS:
        reason = f"Repair limit of {MAX_REPAIR_ROUNDS} rounds reached"
    history.append(codes)
    if reason:
        state["status"] = "FAIL"
    else:
        state["repair_rounds"] = state.get("repair_rounds", 0) + 1
        state["phase"] = "IMPLEMENT"
    write_state(directory, state)
    return state, reason


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="create state.json for a new change")
    init.add_argument("directory", type=Path)
    init.add_argument("--change-id", required=True)

    update = commands.add_parser("update", help="set phase or status and refresh artifact hashes")
    update.add_argument("directory", type=Path)
    update.add_argument("--phase", choices=PHASES)
    update.add_argument("--status", choices=STATUSES)

    repair = commands.add_parser("repair", help="count a repair round after blockers; exits 3 when the loop must stop")
    repair.add_argument("directory", type=Path)
    repair.add_argument("--blockers", required=True, help="comma-separated blocker codes")

    args = parser.parse_args()
    try:
        if args.command == "init":
            state = init_state(args.directory, args.change_id)
        elif args.command == "update":
            state = update_state(args.directory, args.phase, args.status)
        else:
            codes = [code.strip() for code in args.blockers.split(",") if code.strip()]
            state, reason = record_repair(args.directory, codes)
            if reason:
                print(json.dumps({"stop": True, "reason": reason, "state": state}, indent=2))
                return 3
    except (OSError, ValueError) as error:
        print(json.dumps({"error": str(error)}, indent=2), file=sys.stderr)
        return 2

    print(json.dumps(state, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
