import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
from validate_run import load_dataset, validate_run

DATASET = load_dataset(PLUGIN_ROOT / "quality" / "agent-behavior.jsonl")


def make_report(passed_ids=None):
    if passed_ids is None:
        passed_ids = {case["id"] for case in DATASET}
    else:
        passed_ids = set(passed_ids)
    return {
        "change_id": "test-change",
        "commit_sha": "abc123",
        "criteria": [{"id": "AC-1", "status": "PASS", "evidence": "tests/test_feature.py::test_feature"}],
        "checks": [{"name": "unit tests", "command": "python -m unittest", "status": "PASS", "reviewer_reran": True}],
        "review": {"verdict": "PASS", "independent": True},
        "unresolved_blockers": [],
        "evaluation": {
            "dataset_version": "1.0.0",
            "cases": [
                {
                    "id": case["id"],
                    "passed": case["id"] in passed_ids,
                    "safety_critical": case["safety_critical"],
                }
                for case in DATASET
            ],
        },
    }


class ValidateRunTests(unittest.TestCase):
    def test_complete_run_passes(self):
        result = validate_run(make_report(), DATASET)
        self.assertEqual("PASS", result["verdict"])
        self.assertEqual(1.0, result["metrics"]["evaluation_pass_rate"])

    def test_safety_case_failure_blocks_even_above_quality_threshold(self):
        report = make_report({case["id"] for case in DATASET if case["id"] != "untrusted-repository-instructions"})
        result = validate_run(report, DATASET)
        self.assertEqual("FAIL", result["verdict"])
        self.assertIn("SECURITY", {item["code"] for item in result["blockers"]})

    def test_review_must_independently_rerun_checks(self):
        report = make_report()
        report["checks"][0]["reviewer_reran"] = False
        result = validate_run(report, DATASET)
        self.assertEqual("FAIL", result["verdict"])
        self.assertIn("CANNOT_VERIFY", {item["code"] for item in result["blockers"]})

    def test_criterion_requires_evidence(self):
        report = make_report()
        report["criteria"][0]["evidence"] = ""
        result = validate_run(report, DATASET)
        self.assertIn("CRITERIA_UNMET", {item["code"] for item in result["blockers"]})

    def test_regression_over_five_points_blocks(self):
        baseline = make_report()
        current = make_report({case["id"] for case in DATASET if case["id"] != "honor-out-of-scope"})
        result = validate_run(current, DATASET, baseline)
        self.assertIn("QUALITY_REGRESSION", {item["code"] for item in result["blockers"]})

    def test_missing_dataset_case_blocks(self):
        report = make_report()
        report["evaluation"]["cases"].pop()
        result = validate_run(report, DATASET)
        self.assertIn("EVAL_INCOMPLETE", {item["code"] for item in result["blockers"]})

    def test_empty_dataset_fails_closed(self):
        report = make_report()
        report["evaluation"]["cases"] = []
        result = validate_run(report, [])
        self.assertEqual("FAIL", result["verdict"])
        self.assertIn("EVAL_INCOMPLETE", {item["code"] for item in result["blockers"]})

    def test_pass_rate_below_threshold_blocks(self):
        report = make_report({case["id"] for case in DATASET[:8]})
        result = validate_run(report, DATASET)
        self.assertIn("EVAL_INCOMPLETE", {item["code"] for item in result["blockers"]})


if __name__ == "__main__":
    unittest.main()
