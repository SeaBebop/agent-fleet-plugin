# Agent Fleet

A Claude Code plugin for evidence-backed software changes. Agent Fleet provides a manual, quality-gated workflow with focused researcher, implementer, reviewer, and coordinator agents. The Claude plugin format can also be loaded by VS Code's Copilot harness, but component behavior and tool availability vary by harness; verify the workflow in the one you use.

## Status

Version `0.2.0` packages the fleet as a Claude Code plugin. It includes a per-change gate, a state helper that enforces phases and the repair cap, hashed reviewer evidence with a fail-before / pass-after proof for behavior changes, a separate opt-in suite of ten behavior probes, unit tests, and GitHub Actions CI. This version does not install hooks, start MCP servers, deploy infrastructure, or claim measured model-evaluation results.

The workflow has been exercised in Claude Code on Windows through three fleet runs of small changes to this repository. It has not been verified in the Copilot harness. See Harness Compatibility.

## Local Development

Prerequisites: Claude Code for plugin loading, and Python 3.10+ for the offline report gate and tests.

From the repository root:

```powershell
python -m unittest discover -s plugins/agent-fleet/tests -v
python plugins/agent-fleet/tests/check_release_metadata.py
claude plugin validate ./plugins/agent-fleet --strict
claude plugin validate . --strict
claude --plugin-dir ./plugins/agent-fleet
```

In Claude Code, invoke `/agent-fleet:run-change`. The skill is the single workflow definition and runs in your own session; the specialized agents are also available for direct delegation. For a stricter mode where the coordinator has no edit tool, run `fleet-orchestrator` as the main agent (for example `claude --agent agent-fleet:fleet-orchestrator`); it reads and follows the same skill.

In VS Code, choose the GitHub Copilot harness, open Agent Customizations, and install the plugin from the local folder `plugins/agent-fleet` while developing. For a published repository, use the repository's marketplace source. Start with a low-risk task and inspect the agent's available tools and actions: a compatible Claude manifest does not mean every Claude tool or workflow feature behaves identically in Copilot.

## Use It in VS Code

For a local checkout, select the **Copilot** harness, open **Chat: Open Customizations**, choose **Plugins**, and select the `+` button next to **User** or **Workspace**. In the source dialog, choose the local folder `plugins/agent-fleet` inside this repository. That folder contains the plugin's `.claude-plugin/plugin.json` manifest. Install it, start a fresh Copilot session, and invoke `/agent-fleet:run-change`.

For the GitHub-hosted repository, use the marketplace flow instead. The repository root contains `.claude-plugin/marketplace.json`; the install-from-source `+` flow expects a plugin root, which is nested here. In Agent Customizations, open **Plugins > Browse Marketplace > Configure Marketplaces**, add the GitHub repository, browse the `agent-fleet-tools` marketplace, and install **Agent Fleet**. Review the repository and trust prompt before installation.

After installing, confirm the plugin is listed and enabled, start a new Copilot session, and try a low-risk task. Inspect its actions and tool use; format compatibility does not guarantee every Claude-specific feature behaves identically in Copilot.

`claude plugin validate .` checks the marketplace catalog. Validate the plugin directory separately as shown above; the commands have different targets.

The per-change gate and state helper can be run from any consumer repository:

```powershell
python "<path-to-plugin>/scripts/fleet_state.py" init work/<change-id> --change-id <change-id>
python "<path-to-plugin>/scripts/validate_run.py" work/<change-id>
```

The gate requires each contract criterion to have reviewer evidence, every contract check to be rerun by an independent reviewer, no unresolved blockers, at most two repair rounds, and unchanged artifact hashes. Behavior probes are a separate opt-in suite (`plugins/agent-fleet/quality/README.md`), validated with `validate_suite.py`.

The validator checks structure, consistency, and hashes. It does not execute agents, independently verify command output, or score model behavior. Reviewers must record genuine evidence.

## Using the Workflow

Start the message with `/agent-fleet:run-change` as its very first characters, followed by the task and its acceptance criteria. The skill only runs when the name is at the start of the message; a plain prompt, or a name after other text, does not run it and the session does the work itself. Confirm the fleet is running: within its first actions the coordinator creates `work/<change-id>/state.json` at the repository root. Commit or stash unrelated changes first so the reviewer's diff covers only the change.

The fleet costs more time and tokens than a direct edit, so it is not worth it for trivial changes. Its value is the independent review, the gates, and the audit trail.

## Recommended Permission Rules

Agent instructions and tool lists guide behavior; they are not a security boundary. Block risky commands with permission rules, which Claude Code applies to the main session and to subagents. In a consuming repository's `.claude/settings.json`:

```json
{
  "permissions": {
    "deny": [
      "Bash(git push *)",
      "Bash(terraform apply *)",
      "Bash(terraform destroy *)",
      "Bash(rm -rf *)"
    ]
  }
}
```

These rules match command patterns and are not exhaustive; a shell offers many ways to run the same action. On Windows, add equivalents for the PowerShell tool after checking the Claude Code permissions documentation for the syntax. For the Copilot harness, keep terminal commands set to require approval and read each prompt. A deny-list setting for that harness has not been verified here.

## Harness Compatibility

The agents list Claude Code tool names. VS Code documents lowercase aliases for the Copilot harness:

| Claude Code | Copilot alias |
|---|---|
| `Read` | `read` |
| `Grep`, `Glob` | `search` |
| `Edit`, `Write` | `edit` |
| `Bash` | `execute` |
| `Agent` | `agent` |

Whether the Copilot harness translates Claude names in plugin agents, and whether it ignores the Claude-only fields `maxTurns` and `disallowed-tools`, is untested. The skill locates the scripts by glob search if `${CLAUDE_PLUGIN_ROOT}` is not substituted.

Smoke test in each harness with a small change:

1. The plugin is listed and enabled, and `/agent-fleet:run-change` appears.
2. The coordinator creates `work/<change-id>/state.json` at the repository root and records the baseline commit.
3. The researcher (for changes beyond one or two files), implementer, and reviewer are launched, one at a time, with the intended tools.
4. The coordinator never edits source files itself.
5. The reviewer saves files under `evidence/`, and `validate_run.py` prints PASS.

Results so far: Claude Code 2.1.330 on Windows passes all five. Copilot: not yet verified.

## Evaluation Costs

The JSONL behavior probes belong to a separate opt-in suite and are not part of the per-change gate. Claude Code's native `claude plugin eval` suite is also separate and makes real model calls that count against your plan or API bill. It is not run by GitHub Actions in this first version. Add model-backed eval cases and CI credentials only after choosing a budget and deciding which checks justify the cost.

## Install After Publishing

Load from a local checkout with `claude --plugin-dir ./plugins/agent-fleet`.

After the marketplace repository is public, replace `<github-owner>` and `<repository>` with its actual location:

```text
/plugin marketplace add <github-owner>/<repository>
/plugin install agent-fleet@agent-fleet-tools
```

For this setup, the marketplace and plugin live in the same repository; the catalog points to `./plugins/agent-fleet`.
