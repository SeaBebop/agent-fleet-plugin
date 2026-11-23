import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
from validate_suite import load_dataset, validate_suite

DATASET = load_dataset(PLUGIN_ROOT / "quality" / "agent-behavior.jsonl")


def make_report(passed_ids=None):
    if passed_ids is None:
        passed_ids = {case["id"] for case in DATASET}
    else:
        passed_ids = set(passed_ids)
    return {
        "dataset_version": "1.0.0",
        "subject": {"model": "test-model", "plugin_version": "0.0.0"},
        "cases": [
            {"id": case["id"], "passed": case["id"] in passed_ids, "safety_critical": case["safety_critical"]}
            for case in DATASET
        ],
    }


def codes(result):
    return {item["code"] for item in result["blockers"]}


class ValidateSuiteTests(unittest.TestCase):
    def test_complete_suite_passes(self):
        result = validate_suite(make_report(), DATASET)
        self.assertEqual("PASS", result["verdict"])
        self.assertEqual(1.0, result["metrics"]["pass_rate"])

    def test_safety_case_failure_blocks_even_above_quality_threshold(self):
        report = make_report({case["id"] for case in DATASET if case["id"] != "untrusted-repository-instructions"})
        result = validate_suite(report, DATASET)
        self.assertEqual("FAIL", result["verdict"])
        self.assertIn("SECURITY", codes(result))

    def test_regression_over_five_points_blocks(self):
        current = make_report({case["id"] for case in DATASET if case["id"] != "honor-out-of-scope"})
        result = validate_suite(current, DATASET, make_report())
        self.assertIn("QUALITY_REGRESSION", codes(result))

    def test_invalid_baseline_blocks(self):
        result = validate_suite(make_report(), DATASET, {"cases": []})
        self.assertIn("EVAL_INCOMPLETE", codes(result))

    def test_missing_dataset_case_blocks(self):
        report = make_report()
        report["cases"].pop()
        self.assertIn("EVAL_INCOMPLETE", codes(validate_suite(report, DATASET)))

    def test_duplicate_case_blocks(self):
        report = make_report()
        report["cases"].append(dict(report["cases"][0]))
        self.assertIn("EVAL_INCOMPLETE", codes(validate_suite(report, DATASET)))

    def test_safety_flag_mismatch_blocks(self):
        report = make_report()
        report["cases"][0]["safety_critical"] = not report["cases"][0]["safety_critical"]
        self.assertIn("EVAL_INCOMPLETE", codes(validate_suite(report, DATASET)))

    def test_empty_dataset_fails_closed(self):
        result = validate_suite(make_report(), [])
        self.assertEqual("FAIL", result["verdict"])
        self.assertIn("EVAL_INCOMPLETE", codes(result))

    def test_pass_rate_below_threshold_blocks(self):
        report = make_report({case["id"] for case in DATASET[:8]})
        self.assertIn("EVAL_INCOMPLETE", codes(validate_suite(report, DATASET)))

    def test_subject_is_required(self):
        report = make_report()
        del report["subject"]
        self.assertIn("EVAL_INCOMPLETE", codes(validate_suite(report, DATASET)))

    def test_non_object_report_fails(self):
        self.assertIn("GATE_FAILED", codes(validate_suite([], DATASET)))

    def test_duplicate_dataset_ids_are_rejected(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.jsonl"
            line = json.dumps({"id": "a", "safety_critical": False})
            path.write_text(f"{line}\n{line}\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_dataset(path)


if __name__ == "__main__":
    unittest.main()
