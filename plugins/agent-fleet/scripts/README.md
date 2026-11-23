# Scripts

All scripts are offline and use only Python's standard library (3.10+). They take the change directory `work/<change-id>/`.

```powershell
python scripts/fleet_state.py init work/<change-id> --change-id <change-id>
python scripts/fleet_state.py update work/<change-id> --phase REVIEW
python scripts/fleet_state.py repair work/<change-id> --blockers TEST_FAIL,SCOPE_CREEP
python scripts/validate_run.py work/<change-id>
python scripts/validate_suite.py suite-report.json --baseline earlier-suite-report.json
```

- `fleet_state.py` writes `state.json`: phase, status, repair rounds, blocker history, and a SHA-256 for each saved artifact. `update` always refreshes the hashes. `repair` counts a repair round and exits 3 when the two-round limit is reached or the same blockers repeat.
- `validate_run.py` is the per-change gate. It checks that artifacts parse and agree on the change id, every contract criterion has reviewer evidence, the reviewer independently reran every contract check, no blockers remain, the run is in the `VALIDATE` or `DONE` phase with a passing status, and no artifact changed after its hash was recorded. Exit codes: 0 pass, 1 fail, 2 missing directory.
- `validate_suite.py` validates a behavior-probe suite report. See `quality/README.md`.

None of these prove that a command ran or grade an agent; the reviewer must provide real evidence.
