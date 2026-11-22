# Agent Fleet

A Claude Code plugin for evidence-backed software changes. Agent Fleet provides a manual, quality-gated workflow with focused researcher, implementer, reviewer, and coordinator agents. The Claude plugin format can also be loaded by VS Code's Copilot harness, but component behavior and tool availability vary by harness; verify the workflow in the one you use.

## Status

Version `0.1.0` packages the existing fleet template as a Claude Code plugin. It includes a report validator, a versioned set of ten behavior probes, unit tests, and GitHub Actions CI. This version does not install hooks, start MCP servers, deploy infrastructure, or claim measured model-evaluation results.

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

In Claude Code, invoke `/agent-fleet:run-change`. The skill coordinates the workflow; the specialized agents are also available for direct delegation.

In VS Code, choose the GitHub Copilot harness, open Agent Customizations, and install the plugin from the local folder `plugins/agent-fleet` while developing. For a published repository, use the repository's marketplace source. Start with a low-risk task and inspect the agent's available tools and actions: a compatible Claude manifest does not mean every Claude tool or workflow feature behaves identically in Copilot.

## Use It in VS Code

For a local checkout, select the **Copilot** harness, open **Chat: Open Customizations**, choose **Plugins**, and select the `+` button next to **User** or **Workspace**. In the source dialog, choose the local folder `plugins/agent-fleet` inside this repository. That folder contains the plugin's `.claude-plugin/plugin.json` manifest. Install it, start a fresh Copilot session, and invoke `/agent-fleet:run-change`.

For the GitHub-hosted repository, use the marketplace flow instead. The repository root contains `.claude-plugin/marketplace.json`; the install-from-source `+` flow expects a plugin root, which is nested here. In Agent Customizations, open **Plugins > Browse Marketplace > Configure Marketplaces**, add the GitHub repository, browse the `agent-fleet-tools` marketplace, and install **Agent Fleet**. Review the repository and trust prompt before installation.

After installing, confirm the plugin is listed and enabled, start a new Copilot session, and try a low-risk task. Inspect its actions and tool use; format compatibility does not guarantee every Claude-specific feature behaves identically in Copilot.

`claude plugin validate .` checks the marketplace catalog. Validate the plugin directory separately as shown above; the commands have different targets.

The report gate can be run from any consumer repository:

```powershell
python "<path-to-plugin>/scripts/validate_run.py" work/<change-id>/run-report.json
python "<path-to-plugin>/scripts/validate_run.py" work/<change-id>/run-report.json --baseline work/<baseline-change>/run-report.json
```

The validator requires evidence for each acceptance criterion, reviewer-rerun checks, an independent review verdict, no unresolved blockers, a result for each case in `quality/agent-behavior.jsonl`, a 90% overall pass rate, and a 100% pass rate on safety-critical cases. A supplied baseline may not regress by more than five percentage points.

The validator checks report structure and reported scores. It does not execute agents, independently verify command output, or score model behavior. Reviewers must record genuine evidence. Use the same dataset version when comparing a baseline.

## Evaluation Costs

The JSONL behavior probes are included in offline report validation. Claude Code's native `claude plugin eval` suite is separate and makes real model calls that count against your plan or API bill. It is not run by GitHub Actions in this first version. Add model-backed eval cases and CI credentials only after choosing a budget and deciding which checks justify the cost.

## Install After Publishing

Load from a local checkout with `claude --plugin-dir ./plugins/agent-fleet`.

After the marketplace repository is public, replace `<github-owner>` and `<repository>` with its actual location:

```text
/plugin marketplace add <github-owner>/<repository>
/plugin install agent-fleet@agent-fleet-tools
```

For this setup, the marketplace and plugin live in the same repository; the catalog points to `./plugins/agent-fleet`.

## Separate GitHub Account

Copilot's sign-in and GitHub publishing are independent. You can keep VS Code Copilot signed into `marcus_trc`; that does not decide which identity authors commits or authenticates pushes.

Git uses two separate settings:

- **Commit attribution** comes from this repository's local `user.name` and `user.email`. Set the email to one verified on the other GitHub account, or that account's GitHub-provided private `noreply` address, so commits can appear on that profile.
- **Push authentication** comes from the remote URL and SSH key or Git credential. For this one-repository setup, a dedicated SSH host alias is the clearest separation; don't switch global Git identity or the Copilot sign-in.

This folder is an independent Git repository. No remote, GitHub identity, or credentials have been configured. After creating a repository under the other account, set its local author identity and add a remote using an SSH alias:

```powershell
git config --local user.name "Other Account Name"
git config --local user.email "verified-email-or-other-account-noreply-address"
git remote add origin git@github-other:OTHER_USERNAME/agent-fleet-plugin.git
git config --local --get user.email
git remote -v
```

Configure `github-other` in your user SSH config to use a key registered only with the other account, then verify it with `ssh -T git@github-other` before pushing. If using HTTPS and GitHub CLI instead, `gh auth switch --user OTHER_USERNAME` switches the CLI's active account and may affect other CLI operations; it is not required for Copilot. Never put tokens or private keys in this repository or in prompts. Choose a license before publishing publicly.

## Adapted Design Practices

- Keep this as the canonical Claude-format source until a second harness needs different behavior. Do not hand-maintain duplicate prompts; add a small generator and drift check only when there is a concrete compatibility need.
- Keep roles narrow, descriptions actionable, and tool permissions appropriate to each job. Tool lists guide runtime behavior but are not a security boundary.
- Run free structural/unit checks on every change. Model-backed plugin evals are opt-in, cost-bearing experiments; label scores as model-judged unless calibrated against human-reviewed examples.
- Bump the plugin and marketplace entry versions together for releases. CI checks that they remain synchronized.
