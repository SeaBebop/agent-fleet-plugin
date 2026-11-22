---
schema_version: "1.1"
name: clarify-ambiguous-change
description: The workflow should ask for missing acceptance criteria before any edits.
runs: 1
max_turns: 4
timeout_seconds: 180
allowed_tools: [Skill, Agent]
expected_outcome: The plugin skill is invoked and asks focused questions without attempting an edit.
---

/agent-fleet:run-change Add a CSV import feature. I have not decided the file format, target app, or success criteria. Ask what you need before touching files.
