"""Genre-neutral tool, repair-memory and benchmark regressions. No paid API calls."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from agent.benchmark import benchmark, load_suite, metrics
from agent.contracts import validate_plan, write_bundle
from agent.runner import run, verification_score
from agent.state import AgentState, bundle_digest
from agent.planning import startup_only_plan
from agent.provider import ProviderError
from agent.verification import verify
from test_mvp import TempTest, FakeClient, config, example_bundle, example_plan, verifier_result


SUITE = Path(__file__).resolve().parent.parent / "examples" / "benchmark" / "suite.json"


def plan_with_steps(steps):
    plan = example_plan()
    plan["tests"][0]["steps"] = steps + [{"action": "assert", "source": "state", "path": "score", "op": "ge", "value": 0}]
    return plan


class GeneralContractTests(TempTest):
    def test_all_held_out_plans_valid_and_four_distinct_families(self):
        cases = load_suite(SUITE)
        self.assertEqual(len(cases), 4)
        self.assertEqual(len({case["family"] for case in cases}), 4)

    def test_pointer_and_multi_key_contracts(self):
        steps = [{"action": "click", "selector": "canvas", "position": {"x": 1, "y": 2}, "coordinate_space": "canvas"},
                 {"action": "hover", "selector": "canvas"},
                 {"action": "drag", "selector": "canvas", "position": {"x": 1, "y": 2}, "to": {"x": 40, "y": 50}},
                 {"action": "keys", "keys": ["ArrowRight", "Space"], "hold_ms": 100}]
        validate_plan(plan_with_steps(steps))

    def test_bad_pointer_positions_and_keys_rejected(self):
        bad = [{"action": "click", "selector": "canvas", "position": {"x": -1, "y": 0}},
               {"action": "click", "selector": "canvas", "position": {"x": True, "y": 0}},
               {"action": "click", "selector": "canvas", "position": {"x": float("nan"), "y": 0}},
               {"action": "drag", "selector": "canvas", "position": {"x": 1, "y": 0}, "to": {"x": 3, "y": 0}, "steps": 100},
               {"action": "keys", "keys": ["Space", "Space"]},
               {"action": "keys", "keys": []}]
        for step in bad:
            with self.subTest(step=step), self.assertRaises(ValueError):
                validate_plan(plan_with_steps([step]))

    def test_dom_observations(self):
        for source, extra, value in (("count", {}, 3), ("enabled", {}, True),
                                     ("attribute", {"attribute": "data-state"}, "hidden")):
            validate_plan(plan_with_steps([{"action": "assert", "source": source,
                "selector": "button", "op": "eq", "value": value, **extra}]))
        with self.assertRaises(ValueError):
            validate_plan(plan_with_steps([{"action": "assert", "source": "attribute", "selector": "button",
                "attribute": "bad attribute", "op": "eq", "value": "x"}]))

    def test_gameplay_metadata_and_priority(self):
        plan = example_plan()
        plan["gameplay"] = {"interaction_model": "turn_based", "input_mode": "pointer",
                            "core_loop": "Click a legal cell", "invariants": ["Illegal clicks do not consume a turn"]}
        plan["requirements"][0]["priority"] = "core"
        validate_plan(plan)
        plan["gameplay"]["interaction_model"] = "collector_template"
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_old_plans_still_supported(self):
        validate_plan(example_plan())

    def test_nested_state_contract_normalized_without_changing_criteria(self):
        plan = example_plan()
        plan["state_contract"]["player"] = {"x": "number", "y": "number"}
        original = deepcopy(plan)
        normalized = validate_plan(plan)
        self.assertEqual(normalized["state_contract"]["player.x"], "number")
        self.assertEqual(normalized["tests"], original["tests"])
        self.assertEqual(plan, original)

    def test_duplicate_flattened_paths_rejected(self):
        plan = example_plan()
        plan["state_contract"].update({"player.x": "number", "player": {"x": "number"}})
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_supplemental_manual_check_does_not_downgrade_automated_requirement(self):
        plan = example_plan()
        plan["manual_checks"] = [{"requirement_id": "R1", "instruction": "Visually verify actual counter"}]
        normalized = validate_plan(plan)
        self.assertEqual(normalized["requirements"][0]["verification"], "automated")


class RepairMemoryTests(TempTest):
    def test_invalid_plan_can_leave_a_game_but_never_claim_functional_pass(self):
        class Client(FakeClient):
            def ask_json(self, stage, system, prompt):
                self.calls += 1
                return {"supported": True} if stage == "plan" else example_bundle()
        spec = self.root / "spec.md"
        spec.write_text("Synthetic fixture", encoding="utf-8")
        def check(*args, **kwargs):
            result = verifier_result(True)
            result["tests"][0]["id"] = "StartupSurface"
            return result
        code = run(config(), spec, self.root / "run", client_factory=Client, verifier=check,
                   preflight_fn=lambda **kw: {"ok": True})
        summary = json.loads((self.root / "run" / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(code, 2)
        self.assertTrue((self.root / "run" / "game" / "index.html").exists())
        self.assertEqual(summary["planning_status"], "failed_startup_only")
        self.assertTrue(summary["infrastructure_checks_passed"])
        self.assertFalse(summary["automated_checks_passed"])
        self.assertIsNone(summary["automated_requirement_pass_rate"])
        self.assertEqual(summary["requirements"][1]["status"], "manual_pending")

    def test_strict_plan_mode_does_not_degrade(self):
        class Client(FakeClient):
            def ask_json(self, stage, system, prompt):
                self.calls += 1
                return {"supported": True}
        spec = self.root / "spec.md"
        spec.write_text("Synthetic fixture", encoding="utf-8")
        run(config(), spec, self.root / "run", strict_plan=True, client_factory=Client,
            preflight_fn=lambda **kw: {"ok": True})
        self.assertFalse((self.root / "run" / "game").exists())

    def test_provider_errors_never_trigger_startup_only_fallback(self):
        class Client(FakeClient):
            def ask_json(self, *args):
                self.calls += 1
                raise ProviderError("API HTTP 401")
        spec = self.root / "spec.md"
        spec.write_text("Synthetic fixture", encoding="utf-8")
        run(config(), spec, self.root / "run", client_factory=Client,
            preflight_fn=lambda **kw: {"ok": True})
        self.assertFalse((self.root / "run" / "game").exists())

    def test_code_digest_ignores_summary_and_file_order(self):
        a = {"summary": "one", "files": [{"path": "a.js", "content": "a"}, {"path": "index.html", "content": "b"}]}
        b = {"summary": "two", "files": list(reversed(a["files"]))}
        self.assertEqual(bundle_digest(a), bundle_digest(b))

    def test_memory_keeps_recent_evidence(self):
        state = AgentState()
        for i in range(5):
            state.observe(i, str(i), verifier_result(False), "small edit")
        self.assertEqual(len(state.context()["previous_attempts"]), 3)
        self.assertEqual(state.repair_memory[0]["round"], 2)

    def test_launchable_without_errors_beats_runtime_regression(self):
        stable = verifier_result(False)
        broken = verifier_result(False)
        broken["tests"] = [{"id": str(i), "passed": True} for i in range(5)]
        broken["runtime_errors"] = [{"error": "uncaught"}]
        self.assertGreater(verification_score(stable), verification_score(broken))

    def test_repair_uses_best_base_and_keeps_failed_attempt_memory(self):
        prompts, results = [], []
        class Client(FakeClient):
            def ask_json(self, stage, system, prompt):
                self.calls += 1
                if stage == "plan":
                    return example_plan()
                prompts.append(json.loads(prompt))
                return example_bundle(extra=f"/* attempt {len(prompts)} */")
        def check(*args, **kwargs):
            result = verifier_result(False)
            result["smoke"]["passed"] = len(results) != 1
            results.append(result)
            return result
        spec = self.root / "spec.md"
        spec.write_text("Synthetic fixture", encoding="utf-8")
        run(config(), spec, self.root / "run", client_factory=Client, verifier=check,
            preflight_fn=lambda **kw: {"ok": True})
        self.assertIn("attempt 1", prompts[2]["previous_version"]["files"][0]["content"])
        self.assertEqual(len(prompts[2]["repair_memory"]["previous_attempts"]), 2)

    def test_duplicate_code_is_not_retested_forever(self):
        class Client(FakeClient):
            def ask_json(self, stage, system, prompt):
                self.calls += 1
                return example_plan() if stage == "plan" else example_bundle()
        spec = self.root / "spec.md"
        spec.write_text("Synthetic fixture", encoding="utf-8")
        checks = []
        def check(*args, **kwargs):
            checks.append(1)
            return verifier_result(False)
        run(config(), spec, self.root / "run", max_rounds=5, client_factory=Client,
            verifier=check, preflight_fn=lambda **kw: {"ok": True})
        summary = json.loads((self.root / "run" / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(len(checks), 1)
        self.assertFalse(summary["automated_checks_passed"])
        self.assertEqual(summary["stop_reason"], "repeated_source_without_progress")


class BenchmarkTests(TempTest):
    def test_one_bad_plan_does_not_skip_other_game_types(self):
        def runner(cfg, spec, output, **options):
            output.mkdir(parents=True)
            (output / "summary.json").write_text(json.dumps({"usage": {"api_attempts": 2},
                "status": "run_error", "error": "Could not produce a valid test plan"}), encoding="utf-8")
            return 4
        report = benchmark(config(), SUITE, self.root / "bench", runner=runner)
        self.assertEqual(report["metrics"]["attempted"], 4)
        self.assertEqual(report["metrics"]["api_attempts"], 8)

    def test_permanent_auth_failure_stops_further_paid_cases(self):
        def runner(cfg, spec, output, **options):
            output.mkdir(parents=True)
            (output / "summary.json").write_text(json.dumps({"usage": {"api_attempts": 1},
                "status": "run_error", "error": "API HTTP 401; check account"}), encoding="utf-8")
            return 4
        report = benchmark(config(), SUITE, self.root / "bench", runner=runner)
        self.assertEqual(report["metrics"]["attempted"], 1)
        self.assertEqual(report["metrics"]["api_attempts"], 1)

    def test_shared_budget_and_held_out_plan_not_passed_to_runner(self):
        calls = []
        def runner(cfg, spec, output, **options):
            calls.append(options)
            self.assertNotIn("acceptance_plan", options)
            output.mkdir(parents=True)
            write_bundle(example_bundle(), output / "game")
            (output / "summary.json").write_text(json.dumps({"usage": {"api_attempts": options["max_calls"]},
                "status": "checks_failed", "smoke_passed": True, "automated_checks_passed": False}), encoding="utf-8")
            return 2
        def verify_all(game, plan, *args, **kwargs):
            result = verifier_result(True)
            result["tests"] = [{"id": test["id"], "passed": True}
                               for test in json.loads(plan.read_text(encoding="utf-8"))["tests"]]
            return result
        report = benchmark(config(), SUITE, self.root / "benchmark", max_total_calls=7,
                           runner=runner, verifier=verify_all)
        self.assertEqual([call["max_calls"] for call in calls], [5, 2])
        self.assertEqual(report["metrics"]["api_attempts"], 7)
        self.assertEqual(report["metrics"]["scheduled"], 4)
        self.assertEqual(report["metrics"]["independent_pass_rate"], .5)
        self.assertEqual(report["metrics"]["model_plan_pass_rate"], 0)
        self.assertTrue((self.root / "benchmark" / "BENCHMARK.md").is_file())

    def test_suite_rejects_traversal_before_running(self):
        suite = self.root / "suite.json"
        suite.write_text(json.dumps({"cases": [{"id": "one", "family": "board", "spec": "../outside.md",
                                               "acceptance_plan": "x.json"}]}), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_suite(suite)

    def test_interruption_preserves_known_api_attempt_accounting(self):
        def runner(cfg, spec, output, **options):
            output.mkdir(parents=True)
            (output / "summary.json").write_text(json.dumps({"usage": {"api_attempts": 2}}), encoding="utf-8")
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            benchmark(config(), SUITE, self.root / "bench", runner=runner)
        report = json.loads((self.root / "bench" / "benchmark.json").read_text(encoding="utf-8"))
        self.assertEqual(report["metrics"]["api_attempts"], 2)

    def test_macro_metrics_do_not_hide_a_weak_family(self):
        rows = [{"family": "easy", "independent_passed": True} for _ in range(3)]
        rows.append({"family": "hard", "independent_passed": False})
        result = metrics(rows)
        self.assertEqual(result["independent_pass_rate"], .75)
        self.assertEqual(result["macro_family_independent_pass_rate"], .5)
        self.assertIsNone(result["full_game_acceptance_rate"])


@unittest.skipUnless(os.getenv("MVP_BROWSER_TESTS") == "1", "Opt-in real browser; no API calls")
class GeneralBrowserTests(TempTest):
    def check(self, extra, steps):
        game = self.root / "game"
        write_bundle(example_bundle(extra=extra), game)
        plan = self.root / "plan.json"
        plan.write_text(json.dumps(validate_plan(plan_with_steps(steps))), encoding="utf-8")
        return verify(game, plan, self.root / "evidence", timeout=30)

    def test_canvas_click_scales_coordinates_and_records_actions(self):
        extra = '''const canvas=document.querySelector('canvas');canvas.style.width='400px';canvas.style.height='240px';
        canvas.onclick=e=>{const r=canvas.getBoundingClientRect();score=Math.round((e.clientX-r.left)*canvas.width/r.width)};'''
        result = self.check(extra, [{"action": "click", "selector": "canvas", "position": {"x": 50, "y": 40},
                                    "coordinate_space": "canvas"},
                                   {"action": "assert", "source": "state", "path": "score", "op": "eq", "value": 50}])
        self.assertTrue(result["ok"], result)
        action = result["tests"][0]["actions"][0]
        self.assertTrue(action["ok"])
        self.assertEqual(action["result"]["position_css"]["x"], 100)

    def test_dom_count_attribute_and_enabled(self):
        result = self.check("document.querySelector('#increment').setAttribute('data-state','ready');", [
            {"action": "assert", "source": "count", "selector": "button", "op": "eq", "value": 1},
            {"action": "assert", "source": "attribute", "selector": "#increment", "attribute": "data-state", "op": "eq", "value": "ready"},
            {"action": "assert", "source": "enabled", "selector": "#increment", "op": "eq", "value": True}])
        self.assertTrue(result["ok"], result)

    def test_simultaneous_keys_are_released(self):
        result = self.check('''let held={};window.onkeydown=e=>{held[e.key]=true;
        if(held.ArrowRight&&held[' '])score=1};window.onkeyup=e=>{delete held[e.key];
        if(!Object.keys(held).length&&score===1)score=2};''', [
            {"action": "keys", "keys": ["ArrowRight", "Space"], "hold_ms": 100},
            {"action": "assert", "source": "state", "path": "score", "op": "eq", "value": 2}])
        self.assertTrue(result["ok"], result)

    def test_drag_and_hover_normal_pointer_events(self):
        result = self.check('''const canvas=document.querySelector('canvas');canvas.onmousedown=()=>{score=1};
        canvas.onmouseup=()=>{if(score===1)score=2};''', [
            {"action": "hover", "selector": "canvas", "position": {"x": 20, "y": 20}},
            {"action": "drag", "selector": "canvas", "position": {"x": 20, "y": 20}, "to": {"x": 90, "y": 70}},
            {"action": "assert", "source": "state", "path": "score", "op": "eq", "value": 2}])
        self.assertTrue(result["ok"], result)

    def test_outside_pointer_target_fails_honestly(self):
        result = self.check("", [{"action": "click", "selector": "canvas", "position": {"x": 300, "y": 20}}])
        self.assertFalse(result["ok"])
        self.assertFalse(result["tests"][0]["actions"][0]["ok"])

    def test_disabled_control_is_observed_noop_not_forced_or_misdiagnosed(self):
        result = self.check("document.querySelector('#increment').disabled=true;", [
            {"action": "click", "selector": "#increment"},
            {"action": "assert", "source": "state", "path": "score", "op": "eq", "value": 0}])
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["tests"][0]["actions"][0]["result"]["ignored_disabled"])


if __name__ == "__main__":
    unittest.main()
