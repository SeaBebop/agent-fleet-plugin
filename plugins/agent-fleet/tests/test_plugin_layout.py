import json
import re
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLUGIN_ROOT.parents[1]


class PluginLayoutTests(unittest.TestCase):
    def test_marketplace_points_to_the_plugin(self):
        marketplace = json.loads((REPOSITORY_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        entry = next(plugin for plugin in marketplace["plugins"] if plugin["name"] == "agent-fleet")
        plugin_path = REPOSITORY_ROOT / entry["source"]
        plugin = json.loads((plugin_path / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(plugin["name"], entry["name"])
        self.assertEqual(plugin["version"], entry["version"])
        self.assertTrue(marketplace["owner"]["name"].strip())

    def test_agents_have_required_frontmatter(self):
        expected = {"fleet-orchestrator", "researcher", "implementer", "reviewer"}
        actual = {path.stem for path in (PLUGIN_ROOT / "agents").glob("*.md")}
        self.assertEqual(expected, actual)
        for path in (PLUGIN_ROOT / "agents").glob("*.md"):
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"), path.name)
            frontmatter = text.split("---", 2)[1]
            self.assertRegex(frontmatter, r"(?m)^name:\s*\S+")
            self.assertRegex(frontmatter, r"(?m)^description:\s*\S+")

    def test_run_change_skill_and_quality_dataset_exist(self):
        skill = PLUGIN_ROOT / "skills" / "run-change" / "SKILL.md"
        self.assertTrue(skill.is_file())
        self.assertIn("disable-model-invocation: true", skill.read_text(encoding="utf-8"))
        cases = PLUGIN_ROOT / "quality" / "agent-behavior.jsonl"
        records = [json.loads(line) for line in cases.read_text(encoding="utf-8").splitlines() if line.strip()]
        ids = [record["id"] for record in records]
        self.assertGreaterEqual(len(records), 10)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(isinstance(record["safety_critical"], bool) for record in records))

    def test_skill_states_rules_before_workflow(self):
        text = (PLUGIN_ROOT / "skills" / "run-change" / "SKILL.md").read_text(encoding="utf-8")
        self.assertLess(text.index("## Non-negotiable rules"), text.index("## Workflow"))

    def test_skill_scripts_exist_and_phases_are_valid(self):
        text = (PLUGIN_ROOT / "skills" / "run-change" / "SKILL.md").read_text(encoding="utf-8")
        for script in set(re.findall(r"\b([a-z_]+\.py)\b", text)):
            self.assertTrue((PLUGIN_ROOT / "scripts" / script).is_file(), script)
        sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
        from fleet_state import PHASES

        for phase in re.findall(r"--phase ([A-Z]+)", text):
            self.assertIn(phase, PHASES)

    def test_orchestrator_points_to_the_skill_instead_of_copying_it(self):
        text = (PLUGIN_ROOT / "agents" / "fleet-orchestrator.md").read_text(encoding="utf-8")
        self.assertIn("run-change", text)
        self.assertNotRegex(text, r"(?m)^\d+\.\s")
        self.assertLess(len(text.splitlines()), 15)

    def test_subagents_return_the_documented_artifacts(self):
        expected = {"researcher": "contract.json", "implementer": "implementation.json", "reviewer": "review.json"}
        template = (PLUGIN_ROOT / "templates" / "contract.md").read_text(encoding="utf-8")
        for agent, artifact in expected.items():
            text = (PLUGIN_ROOT / "agents" / f"{agent}.md").read_text(encoding="utf-8")
            self.assertIn(artifact, text, agent)
            self.assertIn(artifact, template)
            self.assertRegex(text, r"(?m)^maxTurns:\s*\d+")


    def test_native_plugin_smoke_eval_is_well_formed(self):
        case = PLUGIN_ROOT / "evals" / "clarify-ambiguous-change"
        prompt = (case / "prompt.md").read_text(encoding="utf-8")
        grader = (case / "graders" / "skill-fired.md").read_text(encoding="utf-8")
        self.assertTrue(prompt.startswith("---\n"))
        self.assertIn("/agent-fleet:run-change", prompt)
        self.assertIn("type: tool_used", grader)
        self.assertIn("run-change", grader)


if __name__ == "__main__":
    unittest.main()
