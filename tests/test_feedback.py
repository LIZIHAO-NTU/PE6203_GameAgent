"""Located planning errors and evidence-linked repair; no real model calls."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from agent.contracts import PlanValidationError, bounded_text, validate_plan, test_steps
from agent.feedback import repair_feedback, validation_feedback
from agent.runner import run
from agent.benchmark import load_suite, metrics
from agent.verification import verify
from test_mvp import TempTest, FakeClient, config, example_plan, example_bundle, verifier_result


def failure():
    return {**verifier_result(False), "tests":[{"id":"T1", "passed":False,
        "failed_step":3, "failure_kind":"assertion_mismatch", "error":"Mismatch",
        "observations":[{"step":3,"actual":1,"op":"eq","expected":2,"passed":False}],
        "actions":[{"step":2,"action":"click","arguments":{"selector":"#increment"},"ok":True}]}]}


class LocatedValidationTests(unittest.TestCase):
    def invalid(self, name="T1"):
        plan = example_plan()
        plan["tests"][0]["id"] = name
        plan["tests"][0]["steps"][2]["path"] = "player.x + 1"
        return plan

    def test_step_error_has_machine_readable_location(self):
        with self.assertRaises(PlanValidationError) as caught:
            validate_plan(self.invalid())
        self.assertIn("tests[0] (T1).steps[2]", caught.exception.location)
        self.assertEqual(caught.exception.detail,"Invalid state path")

    def test_setup_and_combined_indices_are_distinct(self):
        plan=self.invalid()
        test=plan["tests"][0]
        test["setup_steps"]=[test["steps"].pop(0)]
        with self.assertRaises(PlanValidationError) as caught:
            validate_plan(plan)
        self.assertIn("steps[1] (combined step 3)",str(caught.exception))

    def test_setup_error_is_located(self):
        plan=example_plan()
        plan["tests"][0]["setup_steps"]=[{"action":"wait","ms":9000}]
        with self.assertRaisesRegex(PlanValidationError,"setup_steps\\[0\\]"):
            validate_plan(plan)

    def test_unknown_action_is_located_without_rewriting(self):
        plan=example_plan()
        plan["tests"][0]["steps"][1]["action"]="teleport"
        saved=deepcopy(plan)
        with self.assertRaisesRegex(PlanValidationError,"steps\\[1\\].*Unsupported"):
            validate_plan(plan)
        self.assertEqual(plan,saved)

    def test_missing_requirement_coverage_is_located(self):
        plan=example_plan()
        plan["requirements"].append({"id":"R2","text":"Another rule","verification":"automated"})
        with self.assertRaises(PlanValidationError) as caught:
            validate_plan(plan)
        self.assertEqual(caught.exception.location,"tests")
        self.assertIn("R2",caught.exception.detail)

    def test_context_reset_after_failure(self):
        with self.assertRaises(ValueError): validate_plan(self.invalid())
        with self.assertRaises(ValueError) as caught: bounded_text(None,"outside")
        self.assertNotIsInstance(caught.exception,PlanValidationError)
        self.assertEqual(str(caught.exception),"Invalid outside")

    def test_context_reset_after_success(self):
        validate_plan(example_plan())
        with self.assertRaises(ValueError) as caught: bounded_text(None,"outside")
        self.assertNotIsInstance(caught.exception,PlanValidationError)

    def test_parallel_context_does_not_leak_test_ids(self):
        def check(name):
            try: validate_plan(self.invalid(name))
            except PlanValidationError as error: return error.location
        with ThreadPoolExecutor(max_workers=2) as pool:
            locations=list(pool.map(check,["First","Second"]))
        self.assertIn("(First)",locations[0])
        self.assertIn("(Second)",locations[1])

    def test_feedback_is_json_and_contains_policy(self):
        try: validate_plan(self.invalid())
        except PlanValidationError as error: packet=validation_feedback(error)
        self.assertIn("T1",packet["location"])
        self.assertIn("Preserve original",packet["policy"])
        json.dumps(packet)

    def test_legacy_error_gets_root_location(self):
        self.assertEqual(validation_feedback(ValueError("x"))["location"],"$")


class RepairPacketTests(unittest.TestCase):
    def test_packet_contains_rule_action_and_actual_expected(self):
        plan=example_plan()
        result=failure()
        packet=repair_feedback(result,plan)
        self.assertEqual(packet["scenarios"][0]["requirements"][0]["id"],"R1")
        self.assertEqual(packet["scenarios"][0]["frozen_action"],plan["tests"][0]["steps"][2])
        self.assertEqual(packet["failed_tests"][0]["observations"][0]["actual"],1)
        self.assertEqual(packet["failed_tests"][0]["observations"][0]["expected"],2)

    def test_does_not_change_plan_or_evidence(self):
        plan,result=example_plan(),failure()
        old_plan,old_result=deepcopy(plan),deepcopy(result)
        repair_feedback(result,plan)
        self.assertEqual(plan,old_plan)
        self.assertEqual(result,old_result)

    def test_missing_step_does_not_guess_an_action(self):
        result=failure()
        result["tests"][0]["failed_step"]=99
        self.assertIsNone(repair_feedback(result,example_plan())["scenarios"][0]["frozen_action"])

    def test_setup_is_in_reproduction(self):
        plan=example_plan()
        test=plan["tests"][0]
        test["setup_steps"]=[test["steps"].pop(0)]
        scenario=repair_feedback(failure(),plan)["scenarios"][0]
        self.assertEqual(scenario["setup_count"],1)
        self.assertEqual(scenario["reproduce"],test_steps(test))

    def test_unknown_test_is_not_given_invented_rules(self):
        result=failure()
        result["tests"][0]["id"]="Unknown"
        packet=repair_feedback(result,example_plan())
        self.assertEqual(packet["scenarios"],[])
        self.assertEqual(packet["scenario_count_omitted"],1)

    def test_passed_checks_are_kept_as_constraints(self):
        result=failure()
        result["tests"].append({"id":"T2","passed":True})
        self.assertEqual(repair_feedback(result,example_plan())["passed_test_ids"],["T2"])

    def test_basis_remains_a_claim_not_verified_truth(self):
        plan=example_plan()
        plan["tests"][0]["evidence"]={"spec_quote":"claim","expected_basis":"claim"}
        scenario=repair_feedback(failure(),plan)["scenarios"][0]
        self.assertIn("claims",scenario["note"])


class BlockedRepairTests(TempTest):
    def execute(self,blocked=None,initial=False,**options):
        stages=[]
        payloads=[]
        original_plan=example_plan()
        original_plan["tests"][0]["steps"][-1]["value"]=2
        blocked=blocked or {"category":"test_issue","reason":"Original rule says +1, actual is 1 but frozen test expects 2","evidence_test_ids":["T1"]}
        class Client(FakeClient):
            def ask_json(self,stage,system,prompt):
                self.calls+=1
                stages.append(stage)
                payloads.append(json.loads(prompt))
                if stage=="plan": return deepcopy(original_plan)
                if stage=="code_1" and not initial: return example_bundle()
                return {"blocked":deepcopy(blocked)}
        spec=self.root/"spec.md"
        spec.write_text("Click adds exactly one to score, initially zero.",encoding="utf-8")
        output=self.root/"run"
        code=run(config(),spec,output,client_factory=Client,
                 preflight_fn=lambda **kw:{"ok":True},verifier=options.pop("verifier",lambda *a,**kw:failure()),**options)
        summary=json.loads((output/"summary.json").read_text(encoding="utf-8"))
        return code,summary,output,stages,payloads,original_plan

    def test_test_issue_preserves_game_and_frozen_assertion(self):
        code,summary,output,stages,payloads,plan=self.execute()
        self.assertEqual(code,2)
        self.assertEqual(summary["status"],"plan_review_required")
        self.assertFalse(summary["automated_checks_passed"])
        self.assertEqual(stages,["plan","code_1","code_2"])
        self.assertEqual(summary["selected_round"],1)
        self.assertEqual(json.loads((output/"traces/plan.json").read_text(encoding="utf-8")),validate_plan(plan))
        self.assertIn("score++;",(output/"game/index.html").read_text(encoding="utf-8"))
        self.assertTrue((output/"traces/repair_blocked.json").is_file())

    def test_repair_prompt_has_located_scenario_and_trace(self):
        _,_,output,_,payloads,_=self.execute()
        self.assertEqual(payloads[-1]["verification_feedback"]["scenarios"][0]["failed_step"],3)
        self.assertTrue((output/"traces/attempts/02/model_feedback.json").is_file())

    def test_uncertain_category_stops_without_success(self):
        _,summary,_,_,_,_=self.execute({"category":"uncertain","reason":"Insufficient evidence","evidence_test_ids":["T1"]})
        self.assertEqual(summary["status"],"plan_review_required")

    def test_nonexistent_evidence_rejected(self):
        code,summary,output,_,_,_=self.execute({"category":"test_issue","reason":"No actual citation","evidence_test_ids":["NotReal"]})
        self.assertEqual(code,4)
        self.assertEqual(summary["status"],"run_error")
        self.assertTrue((output/"game/index.html").is_file())

    def test_code_error_is_not_a_blocked_category(self):
        code,summary,_,_,_,_=self.execute({"category":"code_error","reason":"Fixable code bug","evidence_test_ids":["T1"]})
        self.assertEqual(code,4)
        self.assertNotIn("repair_blocked",summary)

    def test_initial_generation_cannot_claim_verified_block(self):
        code,summary,output,stages,_,_=self.execute(initial=True)
        self.assertEqual(code,4)
        self.assertFalse((output/"game").exists())
        self.assertEqual(stages,["plan","code_1"])


class EvaluationTests(unittest.TestCase):
    def test_joint_success_requires_both_views(self):
        rows=[{"family":"x","attempted":True,"model_plan_passed":True,"independent_passed":False},
              {"family":"x","attempted":True,"model_plan_passed":True,"independent_passed":True}]
        result=metrics(rows)
        self.assertEqual(result["joint_selected_checks_passed"],1)
        self.assertEqual(result["joint_selected_checks_rate_over_attempted"],.5)

    def test_joint_rate_is_unknown_without_attempts(self):
        self.assertIsNone(metrics([])["joint_selected_checks_rate_over_attempted"])

    def test_mixed_fixtures_valid_and_bounded(self):
        suite=load_suite(Path(__file__).resolve().parent.parent/"examples/reliability_1_2/suite.json")
        self.assertEqual(len(suite),2)
        for case in suite:
            plan=validate_plan(json.loads(case["acceptance_plan"].read_text(encoding="utf-8")))
            self.assertTrue(all(len(test_steps(t))<=18 for t in plan["tests"]))


@unittest.skipUnless(os.getenv("MVP_BROWSER_TESTS")=="1","Opt-in real browser; zero API")
class BlockedBrowserTests(TempTest):
    execute = BlockedRepairTests.execute
    def test_actual_mismatch_stops_without_faking_game(self):
        code,summary,output,_,_,_=self.execute(verifier=verify)
        self.assertEqual(code,2)
        self.assertEqual(summary["status"],"plan_review_required")
        path=self.root/"independent.json"
        path.write_text(json.dumps(example_plan()),encoding="utf-8")
        result=verify(output/"game",path,self.root/"independent-evidence",timeout=25)
        self.assertTrue(result["ok"],result)


if __name__=="__main__": unittest.main()
