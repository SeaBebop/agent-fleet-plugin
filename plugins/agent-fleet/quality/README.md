# Behavior-Probe Suite

`agent-behavior.jsonl` is a versioned set of ten probes (four safety-critical) for the plugin's agents and prompts. It is an opt-in suite, separate from the per-change gate: run it when prompts, agents, or the model change, not for every change.

`scripts/validate_suite.py` checks a suite report: one scored result for every probe, subject `model` and `plugin_version` recorded, a 90% pass rate, a 100% pass rate on safety-critical probes, and no more than a five-point regression from a baseline with the same dataset. It also uses the blocker codes `QUALITY_REGRESSION` and `EVAL_INCOMPLETE`.

The suite report shape:

```json
{
  "dataset_version": "1.0.0",
  "subject": {"model": "model-name", "plugin_version": "0.1.0"},
  "cases": [{"id": "case-id", "passed": true, "safety_critical": false}]
}
```

The validator does not execute these prompts or grade an agent. Record a case as passed only after actually exercising the behavior and reviewing the evidence. Do not use fabricated or copied results as portfolio metrics.

For model-backed plugin behavior testing, use the native `claude plugin eval` suite under `evals/`. It makes real model calls and may incur usage or API costs; it is intentionally not part of the default GitHub Actions workflow.
