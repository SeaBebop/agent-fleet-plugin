# Run Report Validator

`validate_run.py` checks a JSON change report against the versioned behavior probes. It is offline and uses only Python's standard library.

```powershell
python scripts/validate_run.py work/<change-id>/run-report.json
python scripts/validate_run.py work/<change-id>/run-report.json --baseline work/<baseline-change>/run-report.json
```

The script validates that criteria have evidence, the reviewer reran checks, review is independent, blockers are clear, and eval scores meet thresholds. It cannot prove a command ran or independently grade an agent; those claims must be grounded in evidence from the reviewer.
