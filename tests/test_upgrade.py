"""v0.2 feedback actions and replay tests; never uses a paid API."""
from copy import deepcopy
import json
import os
from pathlib import Path
from unittest.mock import patch
import unittest

from agent.contracts import plan_warnings, validate_plan, write_bundle
from agent.recheck import recheck
from agent.verification import failure_summary, verify
from agent.verify_worker import run_goal
from test_mvp import TempTest, example_bundle, example_plan, verifier_result


def goal(action="wait_until", timeout=500):
    step = {"action": action, "until": {"source": "state", "path": "score", "op": "eq", "value": 1},
            "timeout_ms": timeout}
    if action == "key_until":
        step["key"] = "ArrowRight"
    if action == "move_to":
        step.update(actor={"x": "cursor.x", "y": "cursor.y"},
                    target={"x": "target.x", "y": "target.y"},
                    keys={"left": "ArrowLeft", "right": "ArrowRight", "up": "ArrowUp", "down": "ArrowDown"})
    return step


def goal_plan(step):
    plan = example_plan()
    plan["tests"][0]["steps"] = [step, {"action": "assert", "source": "state", "path": "score", "op": "eq", "value": 1}]
    return plan


class UpgradeContractTests(TempTest):
    def test_shipped_independent_plan_valid(self):
        path = Path(__file__).resolve().parent.parent / "examples" / "collector_acceptance.json"
        validate_plan(json.loads(path.read_text(encoding="utf-8")))

    def test_three_goal_actions(self):
        for action in ("wait_until", "key_until", "move_to"):
            validate_plan(goal_plan(goal(action)))

    def test_rejects_invalid_goals(self):
        for change in ({"timeout_ms": 9000}, {"timeout_ms": True}, {"poll_ms": 1},
                       {"until": {}}, {"until": {"source": "state", "path": "score", "op": "eq"}}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_plan(goal_plan({**goal(), **change}))

    def test_navigation_contract_restricted(self):
        for change in ({"actor": {"x": "__bad", "y": "cursor.y"}}, {"keys": {}},
                       {"tolerance": 0}, {"tolerance": float("nan")}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_plan(goal_plan({**goal("move_to"), **change}))

    def test_goal_budget_cannot_expand_forever(self):
        plan = example_plan()
        plan["tests"][0]["steps"] = [goal(timeout=8000) for _ in range(6)] + plan["tests"][0]["steps"]
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_goal_capture_reference_validated(self):
        step = goal()
        step["until"].pop("value")
        step["until"]["value_from"] = {"capture": "missing", "path": "score"}
        with self.assertRaises(ValueError):
            validate_plan(goal_plan(step))

    def test_goal_is_not_substitute_for_assertion(self):
        plan = goal_plan(goal())
        plan["tests"][0]["steps"].pop()
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_surface_property(self):
        plan = example_plan()
        plan["tests"][0]["steps"].append({"action": "assert", "source": "surface", "selector": "canvas",
                                           "property": "width", "op": "eq", "value": 200})
        validate_plan(plan)
        plan["tests"][0]["steps"][-1]["property"] = "onclick"
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_plan_warning_does_not_change_plan(self):
        plan = example_plan()
        plan["tests"][0]["steps"].insert(1, {"action": "key", "key": "ArrowRight", "hold_ms": 100})
        frozen = deepcopy(plan)
        self.assertEqual(plan_warnings(plan)[0]["kind"], "fixed_timing_rule_check")
        self.assertEqual(plan, frozen)

    def test_failure_categories_not_automatic_success(self):
        result = verifier_result(False)
        result["tests"][0].update(failure_kind="goal_timeout", needs_test_review=True)
        summary = failure_summary(result)
        self.assertEqual(summary["counts"], {"goal_timeout": 1})
        self.assertEqual(summary["review_test_ids"], ["T1"])
        self.assertFalse(result["ok"])

    def test_prompt_example_valid(self):
        from agent.prompts import PLANNER_SYSTEM
        structure = PLANNER_SYSTEM.split("Example JSON structure (not a game template):\n", 1)[1]
        validate_plan(json.loads(structure))

    def test_key_released_when_wait_raises(self):
        from unittest.mock import Mock
        page = Mock()
        page.wait_for_timeout.side_effect = RuntimeError("closed")
        with patch("agent.verify_worker.state_snapshot", return_value={"score": 0}), self.assertRaises(RuntimeError):
            run_goal(page, goal("key_until"), {})
        page.keyboard.up.assert_called_once_with("ArrowRight")


class RecheckTests(TempTest):
    def prepare(self):
        game = self.root / "game"
        write_bundle(example_bundle(), game)
        plan = self.root / "plan.json"
        plan.write_text(json.dumps(example_plan()), encoding="utf-8")
        return game, plan

    def test_replay_preserves_source_and_does_not_call_provider(self):
        game, plan = self.prepare()
        original = (game / "index.html").read_bytes()
        with patch("agent.provider.ChatClient.ask_json", side_effect=AssertionError("No API allowed")):
            code = recheck(game, plan, self.root / "replay", verifier=lambda *a, **k: verifier_result(True))
        self.assertEqual(code, 0)
        self.assertEqual((game / "index.html").read_bytes(), original)
        report = json.loads((self.root / "replay" / "recheck.json").read_text(encoding="utf-8"))
        self.assertEqual(report["api_calls"], 0)
        self.assertTrue(report["original_run_success_unchanged"])
        self.assertFalse((self.root / "replay" / "summary.json").exists())

    def test_no_existing_or_nested_output(self):
        game, plan = self.prepare()
        for output in (self.root, game / "replay"):
            with self.subTest(output=output), self.assertRaises(ValueError):
                recheck(game, plan, output)

    def test_failed_replay_retains_failure(self):
        game, plan = self.prepare()
        self.assertEqual(recheck(game, plan, self.root / "replay",
                                verifier=lambda *a, **k: verifier_result(False)), 2)


@unittest.skipUnless(os.getenv("MVP_BROWSER_TESTS") == "1", "Opt-in real browser; no API calls")
class UpgradeBrowserTests(TempTest):
    def check(self, bundle, plan):
        game = self.root / "game"
        write_bundle(bundle, game)
        path = self.root / "plan.json"
        path.write_text(json.dumps(validate_plan(plan)), encoding="utf-8")
        return verify(game, path, self.root / "evidence", timeout=30)

    def test_wait_until_observes_async_change(self):
        result = self.check(example_bundle(extra='setTimeout(()=>{score=1},400);'), goal_plan(goal(timeout=2000)))
        self.assertTrue(result["ok"], result)

    def test_key_until_and_surface_measurements(self):
        plan = goal_plan(goal("key_until", 2000))
        plan["tests"][0]["steps"].append({"action": "assert", "source": "surface", "selector": "canvas",
                                           "property": "width", "op": "eq", "value": 200})
        result = self.check(example_bundle(extra='window.onkeydown=e=>{if(e.key==="ArrowRight")score=1};'), plan)
        self.assertTrue(result["ok"], result)

    def test_surface_rejects_wrong_dimensions(self):
        plan = example_plan()
        plan["tests"][0]["steps"].append({"action": "assert", "source": "surface", "selector": "canvas",
                                           "property": "width", "op": "eq", "value": 640})
        result = self.check(example_bundle(), plan)
        self.assertFalse(result["ok"], result)
        observation = result["tests"][0]["observations"][-1]
        self.assertEqual(observation["actual"], 200)
        self.assertEqual(result["tests"][0]["failure_kind"], "assertion_mismatch")

    def test_unreachable_goal_is_honest_failure(self):
        result = self.check(example_bundle(), goal_plan(goal(timeout=200)))
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["tests"][0]["failure_kind"], "goal_timeout")
        self.assertEqual(result["tests"][0]["observations"][0]["last_state"]["score"], 0)

    def test_missing_state_is_contract_failure(self):
        step = goal()
        step["until"]["path"] = "missing"
        result = self.check(example_bundle(), goal_plan(step))
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["tests"][0]["failure_kind"], "state_contract_error")

    def test_navigation_uses_keyboard_for_changing_targets(self):
        # Synthetic cursor fixture for framework testing, never supplied to the model.
        extra = '''let cursor={x:0,y:0}, target={x:90,y:40}, held={};
        window.onkeydown=e=>{held[e.key]=true};window.onkeyup=e=>{held[e.key]=false};
        setInterval(()=>{cursor.x+=(held.ArrowRight?3:0)-(held.ArrowLeft?3:0);
          cursor.y+=(held.ArrowDown?3:0)-(held.ArrowUp?3:0);
          if(score<2&&Math.abs(cursor.x-target.x)<8&&Math.abs(cursor.y-target.y)<8){
            score++;target={x:20,y:100};}},10);
        window.__gameTest.getState=()=>({score,cursor,target});'''
        plan = goal_plan(goal("move_to", 3000))
        second = goal("move_to", 3000)
        second["until"]["value"] = 2
        plan["tests"][0]["steps"] += [second, {"action": "assert", "source": "state", "path": "score", "op": "ge", "value": 2}]
        result = self.check(example_bundle(extra=extra), plan)
        self.assertTrue(result["ok"], result)
        self.assertGreater(result["tests"][0]["observations"][0]["polls"], 1)


if __name__ == "__main__":
    unittest.main()
