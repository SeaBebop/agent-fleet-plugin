import hashlib
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


def write_evidence(directory, name, text):
    """Write a file under evidence/ and return (evidence_file, evidence_sha256)."""
    path = directory / "evidence" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.encode("utf-8")
    path.write_bytes(data)
    return f"evidence/{name}", hashlib.sha256(data).hexdigest()


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
    evidence_file, evidence_sha256 = write_evidence(directory, "unit-tests.txt", "python -m unittest\nOK\n")
    write_json(
        directory,
        "review.json",
        {
            "change_id": CHANGE_ID,
            "commit_sha": "abc1234",
            "verdict": "PASS",
            "independent": True,
            "checks": [
                {
                    "name": "unit tests",
                    "command": "python -m unittest",
                    "status": "PASS",
                    "reviewer_reran": True,
                    "exit_code": 0,
                    "evidence_file": evidence_file,
                    "evidence_sha256": evidence_sha256,
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

    def unit_test_hash(self):
        return hashlib.sha256((self.dir / "evidence" / "unit-tests.txt").read_bytes()).hexdigest()

    def set_regression_proof(self, adjust=None):
        evidence_file, evidence_sha256 = write_evidence(self.dir, "regression-baseline.txt", "1 failed\n")
        proof = {
            "command": "python -m unittest",
            "baseline_exit_code": 1,
            "fixed_exit_code": 0,
            "evidence_file": evidence_file,
            "evidence_sha256": evidence_sha256,
        }
        if adjust is not None:
            adjust(proof)
        self.edit("contract.json", lambda data: data.update(behavior_change=True))
        self.edit("review.json", lambda data: data.update(regression_proof=proof))

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

    def test_failed_check_with_non_zero_exit_code_reports_test_fail(self):
        self.edit("review.json", lambda data: data["checks"][0].update(status="FAIL", exit_code=1))
        self.assertIn("TEST_FAIL", codes(validate_change(self.dir)))

    def test_failed_check_with_missing_exit_code_reports_test_fail(self):
        def fail_without_exit_code(data):
            data["checks"][0].pop("exit_code")
            data["checks"][0]["status"] = "FAIL"

        self.edit("review.json", fail_without_exit_code)
        self.assertIn("TEST_FAIL", codes(validate_change(self.dir)))

    def test_failed_check_with_string_exit_code_reports_test_fail(self):
        self.edit("review.json", lambda data: data["checks"][0].update(status="FAIL", exit_code="1"))
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

    def test_commit_sha_must_be_a_baseline_hash(self):
        for value in ("working-tree", "abc123", "ABC1234", "abc1234 plus edits", 1234567):
            with self.subTest(value=value):
                self.edit("review.json", lambda data: data.update(commit_sha=value))
                self.assertIn("GATE_FAILED", codes(validate_change(self.dir)))

    def test_commit_sha_may_mark_a_working_tree_diff(self):
        self.edit("review.json", lambda data: data.update(commit_sha="abc1234+working-tree"))
        self.assertEqual("PASS", validate_change(self.dir)["verdict"])

    def test_regression_proof_cannot_reuse_a_check_evidence_file(self):
        self.set_regression_proof(
            lambda proof: proof.update(evidence_file="evidence/./unit-tests.txt", evidence_sha256=self.unit_test_hash())
        )
        self.assertIn("CANNOT_VERIFY", codes(validate_change(self.dir)))

    def test_two_checks_cannot_share_an_evidence_file(self):
        def duplicate(data):
            data["checks"].append(dict(data["checks"][0], name="again", command="python -m other"))

        self.edit("review.json", duplicate)
        self.assertIn("CANNOT_VERIFY", codes(validate_change(self.dir)))

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

    def test_check_without_evidence_file_is_cannot_verify(self):
        self.edit("review.json", lambda data: data["checks"][0].pop("evidence_file"))
        self.assertIn("CANNOT_VERIFY", codes(validate_change(self.dir)))

    def test_check_without_evidence_sha256_is_cannot_verify(self):
        self.edit("review.json", lambda data: data["checks"][0].pop("evidence_sha256"))
        self.assertIn("CANNOT_VERIFY", codes(validate_change(self.dir)))

    def test_deleted_evidence_file_is_cannot_verify(self):
        (self.dir / "evidence" / "unit-tests.txt").unlink()
        fleet_state.update_state(self.dir, None, None)
        self.assertIn("CANNOT_VERIFY", codes(validate_change(self.dir)))

    def test_evidence_hash_mismatch_is_cannot_verify(self):
        self.edit("review.json", lambda data: data["checks"][0].update(evidence_sha256="0" * 64))
        self.assertIn("CANNOT_VERIFY", codes(validate_change(self.dir)))

    def test_evidence_edited_after_state_update_is_gate_failed(self):
        (self.dir / "evidence" / "unit-tests.txt").write_text("tampered\n", encoding="utf-8")
        result = validate_change(self.dir)
        self.assertIn("GATE_FAILED", codes(result))
        self.assertTrue(any("changed after" in item["detail"] for item in result["blockers"]))

    def test_evidence_path_escapes_are_cannot_verify(self):
        outside = Path(self._temp.name) / "outside.txt"
        outside.write_text("outside the change directory\n", encoding="utf-8")
        cases = (
            ("evidence/../../../outside.txt", outside),
            (str(outside), outside),
            ("task.md", self.dir / "task.md"),
        )
        for evidence_file, target in cases:
            with self.subTest(evidence_file=evidence_file):
                digest = hashlib.sha256(target.read_bytes()).hexdigest()
                self.edit(
                    "review.json",
                    lambda data, name=evidence_file, sha=digest: data["checks"][0].update(
                        evidence_file=name, evidence_sha256=sha
                    ),
                )
                self.assertIn("CANNOT_VERIFY", codes(validate_change(self.dir)))

    def test_behavior_change_without_regression_proof_is_cannot_verify(self):
        self.edit("contract.json", lambda data: data.update(behavior_change=True))
        self.assertIn("CANNOT_VERIFY", codes(validate_change(self.dir)))

    def test_behavior_change_with_valid_regression_proof_passes(self):
        self.set_regression_proof()
        result = validate_change(self.dir)
        self.assertEqual("PASS", result["verdict"], result["blockers"])

    def test_malformed_regression_proof_is_cannot_verify(self):
        cases = {
            "baseline exit code 0": lambda proof: proof.update(baseline_exit_code=0),
            "baseline exit code string": lambda proof: proof.update(baseline_exit_code="1"),
            "baseline exit code boolean": lambda proof: proof.update(baseline_exit_code=True),
            "baseline exit code missing": lambda proof: proof.pop("baseline_exit_code"),
            "fixed exit code 1": lambda proof: proof.update(fixed_exit_code=1),
            "fixed exit code string": lambda proof: proof.update(fixed_exit_code="0"),
            "empty command": lambda proof: proof.update(command=" "),
            "evidence hash mismatch": lambda proof: proof.update(evidence_sha256="0" * 64),
        }
        for label, adjust in cases.items():
            with self.subTest(label):
                self.set_regression_proof(adjust)
                self.assertIn("CANNOT_VERIFY", codes(validate_change(self.dir)))

    def test_non_boolean_behavior_change_is_gate_failed(self):
        self.edit("contract.json", lambda data: data.update(behavior_change="yes"))
        self.assertIn("GATE_FAILED", codes(validate_change(self.dir)))

    def test_behavior_change_false_without_regression_proof_passes(self):
        self.edit("contract.json", lambda data: data.update(behavior_change=False))
        result = validate_change(self.dir)
        self.assertEqual("PASS", result["verdict"], result["blockers"])


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
