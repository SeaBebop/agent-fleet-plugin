import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import fleet_state


class FleetStateTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.dir = Path(self._temp.name) / "change"

    def test_init_creates_state_and_directory(self):
        state = fleet_state.init_state(self.dir, "add-feature")
        self.assertEqual("INTAKE", state["phase"])
        self.assertEqual("IN_PROGRESS", state["status"])
        self.assertTrue((self.dir / "state.json").is_file())

    def test_init_refuses_existing_state(self):
        fleet_state.init_state(self.dir, "add-feature")
        with self.assertRaises(ValueError):
            fleet_state.init_state(self.dir, "add-feature")

    def test_init_rejects_unsafe_change_ids(self):
        for bad in ("", "Has Caps", "../escape", "-leading", "x" * 65):
            with self.subTest(change_id=bad), self.assertRaises(ValueError):
                fleet_state.init_state(self.dir, bad)

    def test_update_refreshes_artifact_hashes(self):
        fleet_state.init_state(self.dir, "add-feature")
        (self.dir / "task.md").write_text("one", encoding="utf-8")
        first = fleet_state.update_state(self.dir, "RESEARCH", None)["artifacts"]["task.md"]
        (self.dir / "task.md").write_text("two", encoding="utf-8")
        second = fleet_state.update_state(self.dir, None, None)["artifacts"]["task.md"]
        self.assertNotEqual(first, second)
        self.assertEqual("RESEARCH", fleet_state.read_state(self.dir)["phase"])

    def test_evidence_files_are_hashed_under_relative_keys(self):
        fleet_state.init_state(self.dir, "add-feature")
        (self.dir / "evidence").mkdir()
        (self.dir / "evidence" / "a.txt").write_text("one", encoding="utf-8")
        artifacts = fleet_state.update_state(self.dir, None, None)["artifacts"]
        self.assertIn("evidence/a.txt", artifacts)

    def test_editing_evidence_file_changes_its_recorded_hash(self):
        fleet_state.init_state(self.dir, "add-feature")
        (self.dir / "evidence").mkdir()
        (self.dir / "evidence" / "a.txt").write_text("one", encoding="utf-8")
        first = fleet_state.update_state(self.dir, None, None)["artifacts"]["evidence/a.txt"]
        (self.dir / "evidence" / "a.txt").write_text("two", encoding="utf-8")
        second = fleet_state.update_state(self.dir, None, None)["artifacts"]["evidence/a.txt"]
        self.assertNotEqual(first, second)

    def test_nested_evidence_files_are_hashed(self):
        fleet_state.init_state(self.dir, "add-feature")
        (self.dir / "evidence" / "sub").mkdir(parents=True)
        (self.dir / "evidence" / "sub" / "x.txt").write_text("nested", encoding="utf-8")
        artifacts = fleet_state.update_state(self.dir, None, None)["artifacts"]
        self.assertIn("evidence/sub/x.txt", artifacts)

    def test_update_rejects_unknown_values(self):
        fleet_state.init_state(self.dir, "add-feature")
        with self.assertRaises(ValueError):
            fleet_state.update_state(self.dir, "NOPE", None)
        with self.assertRaises(ValueError):
            fleet_state.update_state(self.dir, None, "NOPE")

    def test_repair_counts_rounds_and_returns_to_implement(self):
        fleet_state.init_state(self.dir, "add-feature")
        state, reason = fleet_state.record_repair(self.dir, ["TEST_FAIL"])
        self.assertIsNone(reason)
        self.assertEqual(1, state["repair_rounds"])
        self.assertEqual("IMPLEMENT", state["phase"])

    def test_repair_stops_when_blockers_repeat(self):
        fleet_state.init_state(self.dir, "add-feature")
        fleet_state.record_repair(self.dir, ["TEST_FAIL", "SCOPE_CREEP"])
        state, reason = fleet_state.record_repair(self.dir, ["SCOPE_CREEP", "TEST_FAIL"])
        self.assertIn("repeated", reason)
        self.assertEqual("FAIL", state["status"])
        self.assertEqual(1, state["repair_rounds"])

    def test_repair_stops_at_round_limit(self):
        fleet_state.init_state(self.dir, "add-feature")
        fleet_state.record_repair(self.dir, ["TEST_FAIL"])
        fleet_state.record_repair(self.dir, ["CRITERIA_UNMET"])
        state, reason = fleet_state.record_repair(self.dir, ["SECURITY"])
        self.assertIn("limit", reason)
        self.assertEqual("FAIL", state["status"])
        self.assertEqual(fleet_state.MAX_REPAIR_ROUNDS, state["repair_rounds"])


class CommandLineTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "fleet_state.py"), *args], capture_output=True, text=True, check=False
        )

    def test_exit_codes(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = str(Path(temp) / "change")
            self.assertEqual(0, self.run_cli("init", directory, "--change-id", "add-feature").returncode)
            self.assertEqual(2, self.run_cli("init", directory, "--change-id", "add-feature").returncode)
            self.assertEqual(0, self.run_cli("update", directory, "--phase", "REVIEW").returncode)
            self.assertEqual(0, self.run_cli("repair", directory, "--blockers", "TEST_FAIL").returncode)
            stopped = self.run_cli("repair", directory, "--blockers", "TEST_FAIL")
            self.assertEqual(3, stopped.returncode)
            self.assertTrue(json.loads(stopped.stdout)["stop"])


if __name__ == "__main__":
    unittest.main()
