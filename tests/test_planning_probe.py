"""Zero-API checks for the one-call planner development probe."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from evals.planning_probe import assess


ROOT = Path(__file__).resolve().parent.parent


class PlanningProbeTests(unittest.TestCase):
    def setUp(self):
        self.spec = (ROOT / "examples/benchmark/resource_shop.md").read_text(encoding="utf-8")
        self.plan = json.loads((ROOT / "examples/benchmark/resource_shop.acceptance.json").read_text(encoding="utf-8"))

    def test_assess_reports_structure_without_claiming_semantics(self):
        report = assess(self.plan, self.spec)
        self.assertTrue(report["structurally_valid"])
        self.assertGreater(report["test_count"], 0)
        self.assertTrue(all(1 <= count <= 18 for count in report["combined_steps_by_test"].values()))
        self.assertNotIn("semantically_correct", report)

    def test_assess_rejects_uncovered_automated_requirements(self):
        invalid = deepcopy(self.plan)
        invalid["tests"] = invalid["tests"][:1]
        with self.assertRaises(ValueError):
            assess(invalid, self.spec)


if __name__ == "__main__":
    unittest.main()
