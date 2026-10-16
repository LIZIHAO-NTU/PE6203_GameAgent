"""Bounded multi-issue feedback and reproducible controlled repair evaluation."""
from copy import deepcopy
import json
import os
import unittest

from agent.contracts import validate_plan
from agent.diagnostics import validate_blocked_repair
from agent.feedback import validation_feedback
from agent.verification import verify
from evals.repair_protocol import counter_bundle, counter_plan, run_probes
from test_mvp import TempTest, config, example_plan, verifier_result


def draft_with_errors(count=3):
    plan=example_plan()
    base=deepcopy(plan["tests"][0])
    plan["tests"]=[]
    for index in range(count):
        test=deepcopy(base)
        test["id"]=f"T{index}"
        test["steps"][1]={"action":"wait","ms":9000+index}
        plan["tests"].append(test)
    return plan


def feedback(plan):
    try: validate_plan(plan)
    except ValueError as error: return validation_feedback(error,plan)
    raise AssertionError("Invalid draft unexpectedly accepted")


class MultiIssueTests(unittest.TestCase):
    def test_multiple_tests_reported_in_one_packet(self):
        packet=feedback(draft_with_errors())
        self.assertEqual(len(packet["issues"]),3)
        self.assertEqual(packet["tests_scanned"],3)
        self.assertIn("tests[2] (T2)",packet["issues"][2]["location"])

    def test_primary_issue_not_duplicated(self):
        packet=feedback(draft_with_errors())
        self.assertEqual(packet["issues"][0]["location"],packet["location"])
        self.assertEqual(len({(i["location"],i["detail"]) for i in packet["issues"]}),3)

    def test_feedback_cannot_accept_or_modify_draft(self):
        plan=draft_with_errors()
        old=deepcopy(plan)
        feedback(plan)
        self.assertEqual(plan,old)
        with self.assertRaises(ValueError): validate_plan(plan)

    def test_global_coverage_from_isolation_is_not_reported(self):
        plan=example_plan()
        plan["requirements"].append({"id":"R2","text":"Second rule","verification":"automated"})
        second=deepcopy(plan["tests"][0])
        second.update(id="T2",requirement_ids=["R2"])
        plan["tests"].append(second)
        plan["tests"][0]["steps"][1]={"action":"wait","ms":3000}
        packet=feedback(plan)
        self.assertEqual(len(packet["issues"]),1)
        self.assertNotIn("missing IDs",json.dumps(packet))

    def test_same_test_only_reports_first_known_error(self):
        plan=draft_with_errors(1)
        plan["tests"][0]["steps"][2]["source"]="invented"
        self.assertEqual(len(feedback(plan)["issues"]),1)

    def test_bounded_issue_count_and_explicit_unscanned(self):
        packet=feedback(draft_with_errors(10))
        self.assertEqual(len(packet["issues"]),8)
        self.assertEqual(packet["tests_not_scanned"],2)

    def test_malformed_test_list_does_not_crash_diagnostics(self):
        for tests in (None,False,"not a list",{},[]):
            plan=example_plan()
            plan["tests"]=tests
            packet=feedback(plan)
            self.assertEqual(packet["tests_scanned"],0)

    def test_root_error_preserved(self):
        plan=draft_with_errors()
        plan["supported"]="true"
        packet=feedback(plan)
        self.assertEqual(packet["location"],"$")
        self.assertEqual(len(packet["issues"]),1)

    def test_no_draft_legacy_call_remains_supported(self):
        packet=validation_feedback(ValueError("legacy"))
        self.assertEqual(packet["detail"],"legacy")
        self.assertEqual(len(packet["issues"]),1)

    def test_reproduction_does_not_inherit_previous_test_capture(self):
        plan=example_plan()
        test=deepcopy(plan["tests"][0])
        test["id"]="T2"
        test["steps"][-1].pop("value")
        test["steps"][-1]["value_from"]={"capture":"firstTest","path":"score"}
        plan["tests"][0]["steps"].insert(0,{"action":"capture","name":"firstTest"})
        plan["tests"].append(test)
        self.assertIn("Unknown earlier capture",feedback(plan)["detail"])


class ProbeClient:
    def __init__(self,cfg,trace,max_calls,deadline): self.calls=0
    def ask_json(self,stage,system,prompt):
        self.calls+=1
        payload=json.loads(prompt)
        if payload["frozen_plan"]["tests"][0]["steps"][1]["value"]==2:
            return {"blocked":{"category":"test_issue","reason":"One click must add one, not two","evidence_test_ids":["T1"]}}
        return counter_bundle()
    def usage_summary(self): return {"api_attempts":self.calls}


def fake_verifier(game,plan_path,*args,**kwargs):
    working="score+=1" in (game/"index.html").read_text(encoding="utf-8")
    plan=json.loads(plan_path.read_text(encoding="utf-8"))
    expected=plan["tests"][0]["steps"][1]["value"]
    tests=[{"id":"T1","passed":working and expected==1,"failed_step":2,
            "failure_kind":"assertion_mismatch","observations":[{"actual":int(working),"expected":expected}]},
           {"id":"T2","passed":working,"failed_step":3,"failure_kind":"assertion_mismatch"}]
    return {**verifier_result(all(t["passed"] for t in tests)),"tests":tests}


class ProbeTests(TempTest):
    def execute(self,**options):
        return run_probes(config(),self.root/"probe",client_factory=options.pop("client_factory",ProbeClient),
                          verifier=options.pop("verifier",fake_verifier),preflight_fn=lambda **kw:{"ok":True},**options)

    def test_repair_and_block_both_use_shared_protocol(self):
        report=self.execute(repeats=1)
        self.assertEqual([r["status"] for r in report["rows"]],["repaired_and_checked","appropriate_block"])
        self.assertEqual(report["usage"]["api_attempts"],2)
        self.assertTrue(all(r["source_integrity"] and r["frozen_integrity"] for r in report["rows"]))

    def test_probe_is_not_counted_as_autonomous_generation(self):
        report=self.execute(repeats=1)
        self.assertEqual(report["generation_calls"],0)
        self.assertEqual(report["kind"],"controlled_repair_probe")
        self.assertIsNone(report["full_game_acceptance"])

    def test_budget_skips_are_preserved(self):
        report=self.execute(max_calls=1,repeats=2)
        self.assertEqual(report["scheduled"],4)
        self.assertEqual(report["usage"]["api_attempts"],1)
        self.assertEqual(sum(r["status"]=="skipped_budget" for r in report["rows"]),3)

    def test_initial_fixture_does_not_silently_change(self):
        report=self.execute(repeats=1)
        self.assertIn("score+=0",(self.root/"probe/code_error_01/initial/index.html").read_text(encoding="utf-8"))
        self.assertTrue(report["rows"][0]["source_integrity"])

    def test_false_success_on_bad_injection_is_rejected(self):
        report=self.execute(repeats=1,verifier=lambda *a,**kw:{**verifier_result(True),"tests":[{"id":"T1","passed":True},{"id":"T2","passed":True}]})
        self.assertEqual(report["usage"]["api_attempts"],0)
        self.assertTrue(all(r["status"]=="invalid_injection_or_infrastructure" for r in report["rows"]))

    def test_invalid_mixed_blocked_response_cannot_edit(self):
        class Client(ProbeClient):
            def ask_json(self,*args):
                self.calls+=1
                return {"blocked":{"category":"test_issue","reason":"x","evidence_test_ids":["T1"]},"files":[]}
        report=self.execute(repeats=1,client_factory=Client)
        self.assertTrue(all(r["status"]=="probe_error" for r in report["rows"]))
        self.assertFalse((self.root/"probe/code_error_01/candidate").exists())

    def test_shared_validator_requires_failed_evidence(self):
        with self.assertRaises(ValueError):
            validate_blocked_repair({"blocked":{"category":"test_issue","reason":"x","evidence_test_ids":["T1"]}},verifier_result(True),True)

    def test_blocked_accepts_bounded_non_action_summary(self):
        response={"summary":"The test contradicts the original rule.",
                  "blocked":{"category":"test_issue","reason":"One click is one, not two","evidence_test_ids":["T1"]}}
        evidence={"tests":[{"id":"T1","passed":False}]}
        self.assertEqual(validate_blocked_repair(response,evidence,True),response["blocked"])

    def test_summary_does_not_allow_mutations_or_invalid_values(self):
        evidence={"tests":[{"id":"T1","passed":False}]}
        blocked={"category":"test_issue","reason":"Conflict","evidence_test_ids":["T1"]}
        for extra in ({"summary":"x","files":[]},{"summary":"x","changes":[]},
                      {"summary":False},{"summary":"x"*1501},{"summary":{"action":"edit"}}):
            with self.subTest(extra=extra),self.assertRaises(ValueError):
                validate_blocked_repair({"blocked":blocked,**extra},evidence,True)

    def test_probe_summary_only_metadata_preserves_fixture(self):
        class Client(ProbeClient):
            def ask_json(self,*args):
                response=super().ask_json(*args)
                if "blocked" in response: response["summary"]="Conflict reported without changing code"
                return response
        report=self.execute(repeats=1,client_factory=Client)
        self.assertEqual(report["rows"][1]["status"],"appropriate_block")
        self.assertTrue(report["rows"][1]["source_integrity"])


@unittest.skipUnless(os.getenv("MVP_BROWSER_TESTS")=="1","Opt-in real browser; zero API")
class ControlledBrowserTests(TempTest):
    execute=ProbeTests.execute
    def test_real_browser_repair_and_conflict(self):
        report=self.execute(repeats=1,verifier=verify)
        self.assertEqual(report["completed_expected_behavior"],2)
        self.assertTrue(all(r["independent"]["ok"] for r in report["rows"]))


if __name__=="__main__": unittest.main()
