import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
import fleet_state
from validate_run import validate_change

CHANGE_ID = "test-change"


def write_json(directory, name, value):
    (directory / name).write_text(json.dumps(value), encoding="utf-8")


def build_change(directory, phase="VALIDATE"):
    (directory / "task.md").write_text("Task\n", encoding="utf-8")
    fleet_state.init_state(directory, CHANGE_ID)
    write_json(
        directory,
        "contract.json",
        {
            "change_id": CHANGE_ID,
            "goal": "Do the thing",
            "acceptance_criteria": [{"id": "AC-1", "text": "It works"}, {"id": "AC-2", "text": "It is tested"}],
            "checks": [{"name": "unit tests", "command": "python -m unittest"}],
        },
    )
    write_json(directory, "implementation.json", {"change_id": CHANGE_ID, "files_changed": ["a.py"]})
    write_json(
        directory,
        "review.json",
        {
            "change_id": CHANGE_ID,
            "commit_sha": "abc123",
            "verdict": "PASS",
            "independent": True,
            "checks": [
                {
                    "name": "unit tests",
                    "command": "python -m unittest",
                    "status": "PASS",
                    "reviewer_reran": True,
                    "exit_code": 0,
                }
            ],
            "criteria": [
                {"id": "AC-1", "status": "PASS", "evidence": "tests/test_a.py::test_works"},
                {"id": "AC-2", "status": "PASS", "evidence": "tests/test_a.py::test_covered"},
            ],
            "blockers": [],
        },
    )
    fleet_state.update_state(directory, phase, None)


def codes(result):
    return {item["code"] for item in result["blockers"]}


class ValidateChangeTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.dir = Path(self._temp.name) / "work" / CHANGE_ID
        self.dir.mkdir(parents=True)
        build_change(self.dir)

    def edit(self, name, change):
        path = self.dir / name
        data = json.loads(path.read_text(encoding="utf-8"))
        change(data)
        path.write_text(json.dumps(data), encoding="utf-8")
        fleet_state.update_state(self.dir, None, None)

    def test_complete_change_passes(self):
        result = validate_change(self.dir)
        self.assertEqual("PASS", result["verdict"], result["blockers"])
        self.assertEqual(2, result["metrics"]["criteria_total"])

    def test_done_phase_still_validates(self):
        fleet_state.update_state(self.dir, "DONE", "PASS")
        self.assertEqual("PASS", validate_change(self.dir)["verdict"])

    def test_missing_directory_fails(self):
        self.assertEqual("FAIL", validate_change(self.dir / "missing")["verdict"])

    def test_missing_review_fails(self):
        (self.dir / "review.json").unlink()
        self.assertIn("GATE_FAILED", codes(validate_change(self.dir)))

    def test_malformed_json_fails(self):
        (self.dir / "contract.json").write_text("{not json", encoding="utf-8")
        self.assertIn("GATE_FAILED", codes(validate_change(self.dir)))

    def test_review_must_be_independent(self):
        self.edit("review.json", lambda data: data.update(independent=False))
        self.assertIn("GATE_FAILED", codes(validate_change(self.dir)))

    def test_failed_verdict_fails(self):
        self.edit("review.json", lambda data: data.update(verdict="FAIL"))
        self.assertIn("GATE_FAILED", codes(validate_change(self.dir)))

    def test_reviewer_must_rerun_checks(self):
        self.edit("review.json", lambda data: data["checks"][0].update(reviewer_reran=False))
        self.assertIn("CANNOT_VERIFY", codes(validate_change(self.dir)))

    def test_failed_check_reports_test_fail(self):
        self.edit("review.json", lambda data: data["checks"][0].update(status="FAIL"))
        self.assertIn("TEST_FAIL", codes(validate_change(self.dir)))

    def test_missing_exit_code_is_cannot_verify(self):
        self.edit("review.json", lambda data: data["checks"][0].pop("exit_code"))
        self.assertIn("CANNOT_VERIFY", codes(validate_change(self.dir)))

    def test_string_exit_code_is_cannot_verify(self):
        self.edit("review.json", lambda data: data["checks"][0].update(exit_code="0"))
        self.assertIn("CANNOT_VERIFY", codes(validate_change(self.dir)))

    def test_boolean_exit_code_is_cannot_verify(self):
        self.edit("review.json", lambda data: data["checks"][0].update(exit_code=True))
        self.assertIn("CANNOT_VERIFY", codes(validate_change(self.dir)))

    def test_non_zero_exit_code_is_cannot_verify(self):
        self.edit("review.json", lambda data: data["checks"][0].update(exit_code=1))
        self.assertIn("CANNOT_VERIFY", codes(validate_change(self.dir)))

    def test_contract_check_must_be_rerun(self):
        self.edit("review.json", lambda data: data["checks"][0].update(command="python -m other"))
        self.assertIn("CANNOT_VERIFY", codes(validate_change(self.dir)))

    def test_every_contract_criterion_needs_evidence(self):
        self.edit("review.json", lambda data: data["criteria"].pop())
        self.assertIn("CRITERIA_UNMET", codes(validate_change(self.dir)))

    def test_empty_evidence_fails(self):
        self.edit("review.json", lambda data: data["criteria"][0].update(evidence=" "))
        self.assertIn("CRITERIA_UNMET", codes(validate_change(self.dir)))

    def test_duplicate_criterion_ids_fail(self):
        self.edit("contract.json", lambda data: data["acceptance_criteria"][1].update(id="AC-1"))
        self.assertIn("CRITERIA_UNMET", codes(validate_change(self.dir)))

    def test_unknown_blocker_code_fails(self):
        self.edit("review.json", lambda data: data.update(blockers=[{"code": "MADE_UP", "detail": "x"}]))
        self.assertIn("GATE_FAILED", codes(validate_change(self.dir)))

    def test_unresolved_blocker_fails(self):
        self.edit("review.json", lambda data: data.update(blockers=[{"code": "SECURITY", "detail": "open ingress"}]))
        self.assertEqual("FAIL", validate_change(self.dir)["verdict"])

    def test_missing_commit_sha_fails(self):
        self.edit("review.json", lambda data: data.update(commit_sha=""))
        self.assertIn("GATE_FAILED", codes(validate_change(self.dir)))

    def test_change_id_mismatch_fails(self):
        self.edit("implementation.json", lambda data: data.update(change_id="other"))
        self.assertIn("GATE_FAILED", codes(validate_change(self.dir)))

    def test_artifact_edited_after_state_update_fails(self):
        path = self.dir / "review.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["commit_sha"] = "tampered"
        path.write_text(json.dumps(data), encoding="utf-8")
        result = validate_change(self.dir)
        self.assertEqual("FAIL", result["verdict"])
        self.assertTrue(any("changed after" in item["detail"] for item in result["blockers"]))

    def test_validation_before_validate_phase_fails(self):
        fleet_state.update_state(self.dir, "REVIEW", None)
        self.assertIn("GATE_FAILED", codes(validate_change(self.dir)))

    def test_non_passing_statuses_fail(self):
        for status in ("FAIL", "PARTIAL", "ERROR", "TIMEOUT"):
            with self.subTest(status=status):
                fleet_state.update_state(self.dir, None, status)
                self.assertEqual("FAIL", validate_change(self.dir)["verdict"])

    def test_repair_rounds_above_limit_fail(self):
        state = fleet_state.read_state(self.dir)
        state["repair_rounds"] = fleet_state.MAX_REPAIR_ROUNDS + 1
        fleet_state.write_state(self.dir, state)
        self.assertIn("GATE_FAILED", codes(validate_change(self.dir)))


class CommandLineTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "validate_run.py"), *args], capture_output=True, text=True, check=False
        )

    def test_exit_codes(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / CHANGE_ID
            directory.mkdir()
            build_change(directory)
            passed = self.run_cli(str(directory))
            self.assertEqual(0, passed.returncode, passed.stdout)
            (directory / "review.json").unlink()
            self.assertEqual(1, self.run_cli(str(directory)).returncode)
            self.assertEqual(2, self.run_cli(str(Path(temp) / "missing")).returncode)


if __name__ == "__main__":
    unittest.main()
