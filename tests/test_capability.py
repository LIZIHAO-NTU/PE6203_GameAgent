"""Capability-screening regressions; no paid model calls."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from agent.contracts import lookup, validate_plan, write_bundle
from agent.verification import verify
from agent.benchmark import benchmark, load_suite, metrics
from test_mvp import TempTest, config, example_plan, example_bundle


ROOT = Path(__file__).resolve().parent.parent
SUITE = ROOT / "examples/benchmark/capability_suite.json"


class SnapshotLookupTests(unittest.TestCase):
    def test_nested_array_and_object_paths(self):
        self.assertEqual(lookup({"board": ["X", "O"]}, "board.1"), "O")
        self.assertEqual(lookup({"player": {"x": 0}}, "player.x"), 0)

    def test_flat_dotted_snapshot_is_observed_without_mutation(self):
        snapshot = {"board.0": "X", "player.x": 0, "flag.active": False}
        original = deepcopy(snapshot)
        self.assertEqual(lookup(snapshot, "board.0"), "X")
        self.assertEqual(lookup(snapshot, "player.x"), 0)
        self.assertIs(lookup(snapshot, "flag.active"), False)
        self.assertEqual(snapshot, original)

    def test_agreeing_representations_are_allowed(self):
        self.assertEqual(lookup({"player": {"x": 3}, "player.x": 3}, "player.x"), 3)

    def test_conflicting_representations_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            lookup({"player": {"x": 3}, "player.x": 9}, "player.x")

    def test_missing_values_are_not_invented(self):
        with self.assertRaises((KeyError, IndexError)):
            lookup({"board": []}, "board.0")


class ScreeningMetricsTests(unittest.TestCase):
    def rows(self):
        return [
            {"family": "board", "attempted": True, "status": "checks_failed",
             "launch_passed": True, "model_plan_passed": False, "independent_passed": True},
            {"family": "board", "attempted": True, "status": "automated_passed_manual_pending",
             "launch_passed": True, "model_plan_passed": True, "independent_passed": False},
            {"family": "physics", "attempted": True, "status": "run_error"},
            {"family": "physics", "attempted": False, "status": "skipped_budget_or_prior_error"},
        ]

    def test_denominators_and_unverified_cases_are_explicit(self):
        result = metrics(self.rows())
        self.assertEqual(result["independent_pass_rate"], .25)
        self.assertEqual(result["independent_evaluated"], 2)
        self.assertEqual(result["independent_pass_rate_over_evaluated"], .5)
        self.assertEqual(result["attempted_without_independent_result"], 1)
        self.assertEqual(result["not_attempted"], 1)
        self.assertEqual(result["launch_rate_over_attempted"], 2 / 3)

    def test_disagreement_is_not_an_automatic_bug_diagnosis(self):
        result = metrics(self.rows())
        self.assertEqual(result["self_pass_independent_fail"], 1)
        self.assertEqual(result["self_fail_independent_pass"], 1)
        self.assertIsNone(result["full_game_acceptance_rate"])

    def test_empty_metrics_have_no_fabricated_rates(self):
        result = metrics([])
        self.assertIsNone(result["independent_pass_rate_over_evaluated"])
        self.assertIsNone(result["launch_rate_over_attempted"])

    def test_family_counts_and_statuses_are_available(self):
        result = metrics(self.rows())
        self.assertEqual(result["by_family"]["board"]["independent_evaluated"], 2)
        self.assertEqual(result["status_counts"]["run_error"], 1)


class CapabilitySuiteTests(TempTest):
    def test_transfer_variant_is_a_separate_valid_suite(self):
        cases = load_suite(ROOT / "examples/benchmark/transfer_suite.json")
        self.assertEqual([c["id"] for c in cases], ["inventory_delivery"])
        self.assertNotIn("inventory_delivery", {c["id"] for c in load_suite(SUITE)})

    def test_coverage_error_identifies_missing_automated_requirement(self):
        plan = example_plan()
        plan["requirements"].append({"id": "MissingRule", "text": "Another mandatory rule", "verification": "automated"})
        with self.assertRaisesRegex(ValueError, "missing IDs: MissingRule"):
            validate_plan(plan)

    def test_coverage_error_identifies_missing_manual_requirement(self):
        plan = example_plan()
        plan["requirements"].append({"id": "ManualRule", "text": "Review visuals", "verification": "manual"})
        with self.assertRaisesRegex(ValueError, "missing IDs: ManualRule"):
            validate_plan(plan)

    def test_six_families_have_valid_independent_plans(self):
        cases = load_suite(SUITE)
        self.assertEqual(len(cases), 6)
        self.assertEqual(len({c["family"] for c in cases}), 6)
        for case in cases:
            plan = validate_plan(json.loads(case["acceptance_plan"].read_text(encoding="utf-8")))
            self.assertTrue(plan["supported"])
            self.assertGreaterEqual(len(plan["tests"]), 5)

    def test_changed_held_out_plan_aborts_instead_of_rewriting_score(self):
        spec = self.root / "case.md"
        spec.write_text("Synthetic fixture", encoding="utf-8")
        plan = self.root / "case.json"
        from test_mvp import example_plan
        plan.write_text(json.dumps(example_plan()), encoding="utf-8")
        suite = self.root / "suite.json"
        suite.write_text(json.dumps({"cases": [{"id": "case", "family": "fixture", "spec": "case.md",
                                               "acceptance_plan": "case.json"}]}), encoding="utf-8")
        def runner(cfg, spec_path, output, **options):
            output.mkdir(parents=True)
            (output / "game").mkdir()
            (output / "game/index.html").write_text("fixture", encoding="utf-8")
            (output / "summary.json").write_text(json.dumps({"status": "checks_failed", "usage": {"api_attempts": 2}}), encoding="utf-8")
            changed = example_plan()
            changed["tests"][0]["steps"][-1]["value"] = 999
            plan.write_text(json.dumps(changed), encoding="utf-8")
            return 2
        with self.assertRaisesRegex(RuntimeError, "Frozen benchmark"):
            benchmark(config(), suite, self.root / "bench", runner=runner,
                      verifier=lambda *args, **kwargs: self.fail("Changed acceptance must not run"))
        result = json.loads((self.root / "bench/benchmark.json").read_text(encoding="utf-8"))
        self.assertEqual(result["metrics"]["api_attempts"], 2)
        self.assertEqual(result["cases"][0]["status"], "benchmark_error_or_interrupted")


@unittest.skipUnless(os.getenv("MVP_BROWSER_TESTS") == "1", "Opt-in real browser; zero API calls")
class SnapshotBrowserTests(TempTest):
    def check_snapshot(self, snapshot, working=True):
        game = self.root / "game"
        write_bundle(example_bundle(working, extra="window.__gameTest={getState:()=> (" + snapshot + ")};"), game)
        plan = example_plan()
        plan["state_contract"] = {"counter.score": "Actual live counter"}
        for step in plan["tests"][0]["steps"]:
            if step.get("source") == "state":
                step["path"] = "counter.score"
        path = self.root / "plan.json"
        path.write_text(json.dumps(validate_plan(plan)), encoding="utf-8")
        return verify(game, path, self.root / "evidence", timeout=30)

    def test_literal_dotted_snapshot_follows_actual_input(self):
        result = self.check_snapshot("{'counter.score':score}")
        self.assertTrue(result["ok"], result)

    def test_wrong_flat_value_still_fails(self):
        result = self.check_snapshot("{'counter.score':score}", working=False)
        self.assertFalse(result["ok"])
        self.assertEqual(result["tests"][0]["failure_kind"], "assertion_mismatch")

    def test_conflicting_flat_and_nested_snapshot_is_not_accepted(self):
        result = self.check_snapshot("{counter:{score},'counter.score':score+1}")
        self.assertFalse(result["ok"])
        self.assertEqual(result["tests"][0]["failure_kind"], "state_contract_error")
