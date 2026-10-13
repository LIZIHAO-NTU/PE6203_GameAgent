"""Completion evidence, bounded recovery and live-observation regressions; zero API."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import unittest

from agent.contracts import validate_plan, write_bundle
from agent.planning import startup_only_plan, validate_recovery
from agent.provider import BudgetError, ProviderError
from agent.quality import completion_gate, review_plan
from agent.runner import run, requirement_results
from agent.verification import verify
from test_mvp import TempTest, FakeClient, config, example_plan, example_bundle, verifier_result


def consistency_step(**changes):
    return {"action": "assert_consistent", "source": "text", "selector": "#count",
            "state_path": "score", "coerce": "number", **changes}


class QualityTests(TempTest):
    def test_review_preserves_plan_and_old_plan_works(self):
        plan = example_plan()
        before = deepcopy(plan)
        self.assertEqual(review_plan(plan)["functional_test_ids"], ["T1"])
        self.assertEqual(plan, before)
        self.assertTrue(completion_gate(plan, verifier_result(True), "valid")["passed"])

    def test_empty_evidence_cannot_pass(self):
        result = verifier_result(True)
        result["tests"] = []
        self.assertFalse(completion_gate(example_plan(), result, "valid")["passed"])

    def test_unknown_duplicate_and_missing_ids_cannot_pass(self):
        for tests in [[{"id": "unknown", "passed": True}],
                      [{"id": "T1", "passed": True}] * 2,
                      [{"id": "T1", "passed": True}, {"id": "extra", "passed": True}]]:
            result = {**verifier_result(True), "tests": tests}
            self.assertFalse(completion_gate(example_plan(), result, "valid")["passed"])

    def test_duplicate_evidence_cannot_mark_requirement_passed(self):
        result = {**verifier_result(True), "tests": [{"id": "T1", "passed": True}] * 2}
        self.assertEqual(requirement_results(example_plan(), result)[0]["status"], "not_passed")

    def test_false_missing_and_nonboolean_pass_cannot_pass(self):
        for test in [{"id": "T1", "passed": False}, {"id": "T1"}, {"id": "T1", "passed": 1}]:
            result = {**verifier_result(True), "tests": [test]}
            self.assertFalse(completion_gate(example_plan(), result, "valid")["passed"])

    def test_runtime_infrastructure_and_smoke_failures_block(self):
        for changes in [{"runtime_errors": ["error"]}, {"infrastructure_error": "timeout"},
                        {"smoke": {"passed": False}}, {"ok": False}]:
            result = {**verifier_result(True), **changes}
            self.assertFalse(completion_gate(example_plan(), result, "valid")["passed"])

    def test_startup_only_plan_cannot_claim_functional_pass(self):
        plan = validate_plan(startup_only_plan())
        result = {**verifier_result(True), "tests": [{"id": "StartupSurface", "passed": True}]}
        self.assertFalse(completion_gate(plan, result, "failed_startup_only")["passed"])
        self.assertFalse(completion_gate(plan, result, "valid")["passed"])

    def test_consistency_alone_is_not_rule_verification(self):
        plan = example_plan()
        plan["tests"][0]["steps"] = [{"action": "click", "selector": "#increment"}, consistency_step()]
        validate_plan(plan)
        self.assertFalse(review_plan(plan)["functional_test_ids"])

    def test_visual_requirement_cannot_substitute_for_core_rule(self):
        plan = example_plan()
        plan["requirements"][0]["priority"] = "visual"
        self.assertFalse(review_plan(plan)["functional_test_ids"])

    def test_purpose_labels_are_optional_but_validated(self):
        plan = example_plan()
        plan["tests"][0]["purpose"] = "legal_action"
        validate_plan(plan)
        plan["tests"][0]["purpose"] = "pretend_pass"
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_consistency_contract_and_no_expected_override(self):
        plan = example_plan()
        plan["tests"][0]["steps"].append(consistency_step())
        validate_plan(plan)
        for changes in [{"source": "state"}, {"coerce": "eval"}, {"state_path": "__proto__.x"},
                        {"value": 1}, {"value_from": {}}, {"op": "ne"}]:
            bad = deepcopy(plan)
            bad["tests"][0]["steps"][-1].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_plan(bad)

    def test_recovery_preserves_commitments_and_adds_tests(self):
        previous = example_plan()
        previous["development_plan"] = []  # Invalid structure, expectations still meaningful.
        recovered = example_plan()
        self.assertEqual(validate_recovery(previous, recovered)["tests"], previous["tests"])
        self.assertEqual(previous["development_plan"], [])

    def test_recovery_rejects_removed_changed_or_downgraded_requirement(self):
        old = example_plan()
        for changes in [{"text": "No rules required"}, {"priority": "visual"}, {"id": "Replacement"}]:
            # Priority has to be explicit in the original to be a retained commitment.
            previous = deepcopy(old)
            previous["requirements"][0]["priority"] = "core"
            candidate = deepcopy(previous)
            candidate["requirements"][0].update(changes)
            if "id" in changes:
                candidate["tests"][0]["requirement_ids"] = ["Replacement"]
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_recovery(previous, candidate)
        candidate = deepcopy(old)
        candidate["requirements"].append({"id": "R2", "text": "Other rule", "verification": "automated"})
        candidate["tests"][0]["requirement_ids"] = ["R2"]
        candidate["requirements"][0]["verification"] = "manual"
        candidate["manual_checks"] = [{"requirement_id": "R1", "instruction": "Check later"}]
        with self.assertRaises(ValueError):
            validate_recovery(old, candidate)

    def test_recovery_rejects_changed_or_deleted_assertion(self):
        old = example_plan()
        for remove in (True, False):
            candidate = deepcopy(old)
            if remove:
                candidate["tests"][0]["steps"].pop(0)
            else:
                candidate["tests"][0]["steps"][-1]["value"] = 0
            with self.subTest(remove=remove), self.assertRaises(ValueError):
                validate_recovery(old, candidate)

    def test_recovery_rejects_startup_substitute_and_unsupported(self):
        for candidate in [startup_only_plan(), {"supported": False, "reason": "unsupported"}]:
            with self.assertRaises(ValueError):
                validate_recovery({"supported": True}, candidate)


class RecoveryControllerTests(TempTest):
    def invoke(self, recovery=example_plan, max_calls=5, strict=False, recover_error=None):
        stages, prompts, verified_plans = [], [], []
        class Client(FakeClient):
            def __init__(self, cfg, trace, limit, deadline):
                super().__init__(cfg, trace, limit, deadline)
                self.limit = limit
            def ask_json(self, stage, system, prompt):
                if self.calls >= self.limit:
                    raise BudgetError("test shared budget")
                self.calls += 1
                stages.append(stage)
                prompts.append(json.loads(prompt))
                if stage == "plan":
                    return {"supported": True}
                if stage == "plan_recovery":
                    if recover_error:
                        raise recover_error
                    return recovery()
                return example_bundle(working=stage == "code_2")
        def checker(game, plan_path, *args, **kwargs):
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            verified_plans.append(plan)
            startup = plan["tests"][0]["id"] == "StartupSurface"
            result = verifier_result(startup or "score++;" in (game / "index.html").read_text(encoding="utf-8"))
            result["tests"][0]["id"] = "StartupSurface" if startup else "T1"
            return result
        spec = self.root / "spec.md"
        spec.write_text("A synthetic counter must increment on click", encoding="utf-8")
        output = self.root / "run"
        code = run(config(), spec, output, max_calls=max_calls, strict_plan=strict,
                   client_factory=Client, verifier=checker, preflight_fn=lambda **kw: {"ok": True})
        summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
        return code, summary, output, stages, prompts, verified_plans

    def test_recovery_retests_then_repairs_under_shared_budget(self):
        code, summary, output, stages, prompts, plans = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(stages, ["plan", "plan", "code_1", "plan_recovery", "code_2"])
        self.assertEqual(summary["usage"]["api_attempts"], 5)
        self.assertEqual(summary["planning_status"], "recovered")
        self.assertTrue(summary["planning_recovered"])
        self.assertTrue(summary["quality_gate"]["passed"])
        self.assertEqual(summary["active_plan"], "functional_plan.json")
        self.assertEqual(summary["selected_round"], 2)
        self.assertEqual(plans[0]["tests"][0]["id"], "StartupSurface")
        self.assertEqual(plans[1]["tests"][0]["id"], "T1")
        initial = output / "traces/plan.json"
        self.assertEqual(hashlib.sha256(initial.read_bytes()).hexdigest(), summary["initial_plan_sha256"])
        self.assertNotEqual(summary["initial_plan_sha256"], summary["plan_sha256"])
        self.assertNotIn("previous_version", prompts[3])
        self.assertNotIn("verification_feedback", prompts[3])
        self.assertTrue(prompts[3]["recovery_mode"])
        self.assertEqual(prompts[4]["planning_status"], "recovered")
        self.assertIsNone(summary["full_game_acceptance"])
        checkpoint = json.loads((output / "traces/state.json").read_text(encoding="utf-8"))
        self.assertEqual(checkpoint["remaining_calls"], 0)

    def test_no_budget_leaves_partial_game_without_recovery(self):
        code, summary, output, stages, *_ = self.invoke(max_calls=3)
        self.assertEqual(code, 2)
        self.assertNotIn("plan_recovery", stages)
        self.assertFalse(summary["planning_recovery_attempted"])
        self.assertEqual(summary["status"], "partial_game_plan_failed")
        self.assertTrue((output / "game/index.html").exists())

    def test_recovery_failure_preserves_partial_game_and_only_tries_once(self):
        for index, error in enumerate([None, ProviderError("API HTTP 401")]):
            if index:
                # Each run uses a new task-local output without overwriting the first.
                self.root = self.root / "second"
                self.root.mkdir()
            code, summary, output, stages, *_ = self.invoke(recovery=startup_only_plan, recover_error=error)
            self.assertEqual(code, 2)
            self.assertEqual(stages.count("plan_recovery"), 1)
            self.assertFalse(summary["planning_recovered"])
            self.assertTrue((output / "game/index.html").exists())
            self.assertFalse((output / "traces/functional_plan.json").exists())
            self.assertFalse(summary["automated_checks_passed"])

    def test_strict_mode_never_generates_or_recovers(self):
        _, summary, output, stages, *_ = self.invoke(strict=True)
        self.assertEqual(stages, ["plan", "plan"])
        self.assertFalse((output / "game").exists())
        self.assertFalse(summary["planning_recovery_attempted"])

    def test_missing_test_results_not_trusted_by_runner(self):
        spec = self.root / "spec.md"
        spec.write_text("Synthetic fixture", encoding="utf-8")
        result = {**verifier_result(True), "tests": []}
        output = self.root / "run"
        code = run(config(), spec, output, max_rounds=1, client_factory=FakeClient,
                   verifier=lambda *a, **k: result, preflight_fn=lambda **kw: {"ok": True})
        summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(code, 2)
        self.assertFalse(summary["automated_checks_passed"])
        self.assertFalse(summary["quality_gate"]["evidence_complete"])

    def test_changed_frozen_plan_cannot_report_success(self):
        spec = self.root / "spec.md"
        spec.write_text("Synthetic fixture", encoding="utf-8")
        def checker(game, plan, *args, **kwargs):
            plan.write_text("{}", encoding="utf-8")
            return verifier_result(True)
        output = self.root / "run"
        run(config(), spec, output, client_factory=FakeClient,
            verifier=checker, preflight_fn=lambda **kw: {"ok": True})
        summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["status"], "run_error")
        self.assertFalse(summary["automated_checks_passed"])
        self.assertTrue(summary["preserved_unverified_candidate"])
        self.assertTrue((output / "game/index.html").is_file())

    def test_observation_only_plan_stops_as_unverified_not_success(self):
        class Client(FakeClient):
            def ask_json(self, stage, system, prompt):
                self.calls += 1
                if stage == "plan":
                    plan = example_plan()
                    plan["tests"][0]["steps"].pop(1)
                    return plan
                return example_bundle()
        spec = self.root / "spec.md"
        spec.write_text("Synthetic fixture", encoding="utf-8")
        output = self.root / "run"
        code = run(config(), spec, output, client_factory=Client,
                   verifier=lambda *a, **k: verifier_result(True), preflight_fn=lambda **kw: {"ok": True})
        summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(code, 2)
        self.assertEqual(summary["status"], "partial_game_evidence_missing")
        self.assertEqual(summary["usage"]["api_attempts"], 2)
        self.assertFalse(summary["automated_checks_passed"])


@unittest.skipUnless(os.getenv("MVP_BROWSER_TESTS") == "1", "Opt-in real browser; zero API")
class ConsistencyBrowserTests(TempTest):
    def check(self, stale=False, extra="", steps=None):
        bundle = example_bundle(extra='''
          const count=document.createElement('span');count.id='count';count.textContent='0';document.body.append(count);
          document.querySelector('#increment').onclick=()=>{count.textContent='1';''' +
          ('' if stale else 'score++;') + '};' + extra)
        game = self.root / "game"
        write_bundle(bundle, game)
        plan = example_plan()
        plan["tests"][0]["steps"] = steps or [
            {"action": "click", "selector": "#increment"}, consistency_step(),
            {"action": "assert", "source": "text", "selector": "#count", "op": "eq", "value": "1"}]
        plan_path = self.root / "plan.json"
        plan_path.write_text(json.dumps(validate_plan(plan)), encoding="utf-8")
        return verify(game, plan_path, self.root / "evidence", timeout=30)

    def test_dom_and_live_snapshot_match(self):
        result = self.check()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["tests"][0]["observations"][0]["actual"], 1)

    def test_stale_snapshot_detected_even_when_page_has_no_runtime_error(self):
        result = self.check(stale=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["runtime_errors"], [])
        test = result["tests"][0]
        self.assertEqual(test["failure_kind"], "state_dom_mismatch")
        self.assertEqual(test["observations"][0]["actual"], 1)
        self.assertEqual(test["observations"][0]["expected"], 0)

    def test_attribute_cross_observation(self):
        result = self.check(extra="document.querySelector('#increment').dataset.value='0';", steps=[
            {"action": "assert_consistent", "source": "attribute", "selector": "#increment",
             "attribute": "data-value", "state_path": "score", "coerce": "number"}])
        self.assertTrue(result["ok"], result)

    def test_non_numeric_dom_is_not_coerced_to_fake_success(self):
        result = self.check(extra="count.textContent='NaN';", steps=[consistency_step()])
        self.assertFalse(result["ok"])
        self.assertEqual(result["tests"][0]["failure_kind"], "state_contract_error")


if __name__ == "__main__":
    unittest.main()
