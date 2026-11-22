# Offline Behavior Probes

`agent-behavior.jsonl` is a versioned probe set used to validate the shape and completeness of submitted run reports. Each case records expected behavior and whether it is safety-critical.

The Python validator does not execute these prompts or grade an agent. Record a case as passed only after actually exercising the behavior and reviewing evidence. Do not use fabricated or copied results as portfolio metrics.

For model-backed plugin behavior testing, use the native `claude plugin eval` suite under `evals/`. It makes real model calls and may incur usage or API costs; it is intentionally not part of the default GitHub Actions workflow.
