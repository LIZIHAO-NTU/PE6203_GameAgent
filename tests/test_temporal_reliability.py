"""Trusted stability observation and advisory test-basis review; no paid API calls."""
from copy import deepcopy
import json
import os
import unittest

from agent.contracts import validate_plan, write_bundle
from agent.plan_review import inspect_plan, validate_audit
from agent.planning import validate_recovery
from agent.quality import review_plan
from agent.diagnostics import route_failure
from agent.verification import verify
from test_mvp import TempTest, example_plan, example_bundle


def stable(**extra):
    return {"action": "assert_stable", "source": "state", "path": "score",
            "duration_ms": 200, "samples": 3, **extra}


def with_steps(steps):
    plan = example_plan()
    plan["tests"][0]["steps"] = steps
    return plan


def temporal_plan(after_pause=False):
    plan = example_plan()
    plan["gameplay"] = {"interaction_model": "real_time", "input_mode": "pointer",
                        "core_loop": "Running counter", "invariants": ["Pause freezes counter"]}
    capture = {"action": "capture", "name": "paused"}
    pause = {"action": "click", "selector": "#pause"}
    plan["tests"][0]["steps"] = ([pause, capture] if after_pause else [capture, pause]) + [
        {"action": "wait", "ms": 100},
        {"action": "assert", "source": "state", "path": "score", "op": "eq",
         "value_from": {"capture": "paused", "path": "score"}}]
    return plan


class StabilityContractTests(unittest.TestCase):
    def test_stability_is_a_bounded_assertion(self):
        self.assertTrue(validate_plan(with_steps([stable()]))["supported"])

    def test_dom_stability_is_supported(self):
        action = {"action": "assert_stable", "source": "text", "selector": "#score",
                  "duration_ms": 200}
        self.assertTrue(validate_plan(with_steps([action]))["supported"])

    def test_stability_cannot_override_expected_values(self):
        for field, value in [("op", "ne"), ("value", 1), ("value_from", {"capture": "x", "path": "score"})]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_plan(with_steps([stable(**{field: value})]))

    def test_stability_rejects_invalid_limits(self):
        for changes in [{"duration_ms": 0}, {"duration_ms": 2001}, {"samples": 1}, {"samples": 9}, {"samples": True}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_plan(with_steps([stable(**changes)]))

    def test_stability_waits_count_toward_total_budget(self):
        plan = with_steps([stable(duration_ms=2000)] * 12)
        other = deepcopy(plan["tests"][0])
        other["id"] = "T2"
        plan["tests"].append(other)
        with self.assertRaisesRegex(ValueError, "45 seconds"):
            validate_plan(plan)

    def test_input_followed_by_stability_counts_as_functional_evidence(self):
        plan = with_steps([{"action": "click", "selector": "#pause"}, stable()])
        self.assertEqual(review_plan(validate_plan(plan))["functional_test_ids"], ["T1"])

    def test_recovery_cannot_weaken_stability_duration(self):
        old = with_steps([{"action": "click", "selector": "#pause"}, stable()])
        changed = deepcopy(old)
        changed["tests"][0]["steps"][-1]["duration_ms"] = 100
        with self.assertRaisesRegex(ValueError, "assertion"):
            validate_recovery(old, changed)

    def test_audit_cannot_weaken_stability(self):
        old = validate_plan(with_steps([{"action": "click", "selector": "#pause"}, stable()]))
        changed = deepcopy(old)
        changed["tests"][0]["steps"][-1]["samples"] = 2
        response = {"status": "revised", "reason": "change samples",
                    "issues": [{"test_id": "T1", "reason": "change", "spec_evidence": "pause"}], "plan": changed}
        with self.assertRaisesRegex(ValueError, "assertions"):
            validate_audit(response, old)


class TestBasisReviewTests(unittest.TestCase):
    def test_unsupported_plan_can_have_null_gameplay_metadata(self):
        self.assertFalse(inspect_plan({"supported": False, "reason": "Out of scope", "gameplay": None})["warnings"])

    def test_basis_is_optional_for_legacy_plans(self):
        self.assertTrue(validate_plan(example_plan())["supported"])

    def test_basis_shape_is_validated(self):
        for basis in [[], {}, {"spec_quote": "x", "expected_basis": ""},
                      {"spec_quote": "x", "expected_basis": "y", "extra": True}]:
            plan = example_plan()
            plan["tests"][0]["evidence"] = basis
            with self.subTest(basis=basis), self.assertRaises(ValueError):
                validate_plan(plan)

    def test_unmatched_quote_is_advisory_and_does_not_mutate(self):
        plan = example_plan()
        plan["tests"][0]["evidence"] = {"spec_quote": "Starts at ninety", "expected_basis": "Initial value"}
        original = deepcopy(plan)
        warnings = inspect_plan(plan, "Starts at zero")['warnings']
        self.assertEqual(warnings[0]["kind"], "unmatched_spec_quote")
        self.assertFalse(warnings[0]["blocking_failure_review"])
        self.assertEqual(plan, original)
        self.assertEqual(route_failure({"tests": [{"id": "T1", "passed": False}]}, {"warnings": warnings})["action"], "repair_code")

    def test_exact_quote_is_not_proof_but_has_no_quote_warning(self):
        plan = example_plan()
        plan["tests"][0]["evidence"] = {"spec_quote": "Starts at zero", "expected_basis": "Zero initially"}
        self.assertFalse(inspect_plan(plan, "Starts at zero. Click once.")["warnings"])

    def test_capture_before_control_change_is_flagged(self):
        warnings = inspect_plan(temporal_plan())["warnings"]
        self.assertEqual(warnings[0]["kind"], "stale_temporal_capture")
        self.assertTrue(warnings[0]["blocking_failure_review"])

    def test_capture_after_control_change_is_not_flagged(self):
        self.assertFalse(inspect_plan(temporal_plan(True))["warnings"])

    def test_turn_based_invalid_action_can_preserve_a_capture(self):
        plan = temporal_plan()
        plan["gameplay"]["interaction_model"] = "turn_based"
        self.assertFalse(inspect_plan(plan)["warnings"])

    def test_stale_capture_with_a_different_path_is_not_flagged(self):
        plan = temporal_plan()
        plan["tests"][0]["steps"][-1]["path"] = "other"
        self.assertFalse(inspect_plan(plan)["warnings"])


@unittest.skipUnless(os.getenv("MVP_BROWSER_TESTS") == "1", "Opt-in real browser; zero API")
class StabilityBrowserTests(TempTest):
    def execute(self, extra, steps):
        game = self.root / "game"
        write_bundle(example_bundle(extra=extra), game)
        plan = self.root / "plan.json"
        plan.write_text(json.dumps(validate_plan(with_steps(steps))), encoding="utf-8")
        return verify(game, plan, self.root / "evidence", timeout=25)

    def test_real_unchanged_state_passes_and_records_samples(self):
        result = self.execute("", [stable()])
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(result["tests"][0]["observations"][0]["samples"]), 3)

    def test_real_moving_state_fails_without_rewriting_it(self):
        result = self.execute("setInterval(()=>score++,30);", [stable()])
        self.assertFalse(result["ok"])
        self.assertEqual(result["tests"][0]["failure_kind"], "assertion_mismatch")

    def test_capture_after_pause_and_resume_uses_normal_inputs(self):
        extra = '''let paused=false; const pause=document.createElement('button');pause.id='pause';pause.textContent='Pause';
        document.body.append(pause);pause.onclick=()=>{paused=!paused};setInterval(()=>{if(!paused)score++},30);'''
        result = self.execute(extra, [{"action": "click", "selector": "#pause"}, stable(),
            {"action": "capture", "name": "paused"}, {"action": "click", "selector": "#pause"},
            {"action": "wait", "ms": 150}, {"action": "assert", "source": "state", "path": "score",
             "op": "gt", "value_from": {"capture": "paused", "path": "score"}}])
        self.assertTrue(result["ok"], result)

    def test_visible_text_stability_uses_dom(self):
        result = self.execute("", [{"action": "assert_stable", "source": "text", "selector": "#increment", "duration_ms": 100}])
        self.assertTrue(result["ok"], result)


if __name__ == "__main__":
    unittest.main()
