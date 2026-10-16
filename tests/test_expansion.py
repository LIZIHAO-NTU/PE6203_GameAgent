"""Structured expectations, native form inputs and read-only dashboard regressions."""
from copy import deepcopy
import json
import os
from pathlib import Path
import threading
import unittest
import urllib.error
import urllib.request

from agent.contracts import validate_plan, write_bundle
from agent.dashboard import make_dashboard_server, render_dashboard, snapshot
from agent.planning import validate_recovery
from agent.quality import review_plan
from agent.verification import verify
from test_mvp import TempTest, example_plan, example_bundle, FakeClient, config, verifier_result
from agent.runner import run
from agent.prompts import planner_system, STRUCTURED_EXPECTATIONS_POLICY


def plan_steps(steps):
    plan = example_plan()
    plan["tests"][0]["steps"] = steps
    return plan


def basis_plan(value=1):
    plan = plan_steps([{"action":"click","selector":"#increment"},
        {"action":"assert","source":"state","path":"score","op":"eq","value":1}])
    plan["tests"][0]["evidence"] = {"spec_quote":"Click increases counter", "expected_basis":"One click gives one",
        "expected_observations":[{"step":2,"value":value}]}
    return plan


class ExpectationModeTests(TempTest):
    def execute(self, enabled):
        systems = []
        class Client(FakeClient):
            def ask_json(self, stage, system, prompt):
                systems.append((stage, system))
                return super().ask_json(stage, system, prompt)
        spec = self.root / "spec.md"
        spec.write_text("Synthetic counter fixture", encoding="utf-8")
        output = self.root / "run"
        code = run(config(), spec, output, client_factory=Client,
                   verifier=lambda *a, **kw: verifier_result(True),
                   preflight_fn=lambda **kw: {"ok":True}, structured_expectations=enabled)
        summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(code, 0)
        self.assertIs(summary["features"]["structured_expectations"], enabled)
        self.assertEqual(systems[0][1], planner_system(enabled))
        self.assertEqual(STRUCTURED_EXPECTATIONS_POLICY in systems[0][1], enabled)

    def test_default_keeps_duplicate_summary_requests_off(self):
        self.execute(False)

    def test_optin_requests_and_records_summary_policy(self):
        self.execute(True)

    def test_nonboolean_mode_rejected_before_any_work(self):
        with self.assertRaisesRegex(ValueError, "boolean"):
            run(config(), self.root / "missing.md", self.root / "run", structured_expectations="yes")


class ExpectedSummaryTests(unittest.TestCase):
    def test_ordered_summary_accepted(self):
        plan = basis_plan()
        plan["tests"][0]["evidence"]["expected_observations"] = [{"value":1}]
        self.assertTrue(validate_plan(plan)["supported"])

    def test_ordered_mismatch_rejected(self):
        plan = basis_plan()
        plan["tests"][0]["evidence"]["expected_observations"] = [{"value":3}]
        with self.assertRaisesRegex(ValueError, "disagrees"):
            validate_plan(plan)

    def test_empty_summary_when_no_literal_assertions(self):
        plan = basis_plan()
        plan["tests"][0]["steps"] = [
            {"action":"capture", "name":"before"},
            {"action":"assert", "source":"state", "path":"score", "op":"eq",
             "value_from":{"capture":"before", "path":"score"}}]
        plan["tests"][0]["evidence"]["expected_observations"] = []
        self.assertTrue(validate_plan(plan)["supported"])

    def test_consistent_summary_accepted(self):
        self.assertTrue(validate_plan(basis_plan())["supported"])

    def test_wrong_numeric_assertion_rejected_before_freeze(self):
        with self.assertRaisesRegex(ValueError,"disagrees"):
            validate_plan(basis_plan(3))

    def test_boolean_is_not_numeric_one(self):
        with self.assertRaises(ValueError):
            validate_plan(basis_plan(True))

    def test_unknown_duplicate_or_noninteger_steps_rejected(self):
        for records in [[{"step":1,"value":1}],[{"step":2,"value":1}]*2,[{"step":True,"value":1}],[]]:
            plan = basis_plan()
            plan["tests"][0]["evidence"]["expected_observations"] = records
            with self.subTest(records=records),self.assertRaises(ValueError):
                validate_plan(plan)

    def test_every_literal_assertion_needs_summary(self):
        plan = basis_plan()
        plan["tests"][0]["steps"].append({"action":"assert","source":"state","path":"score","op":"ge","value":0})
        with self.assertRaisesRegex(ValueError,"cover every"):
            validate_plan(plan)

    def test_combined_setup_step_index_is_used(self):
        plan = basis_plan()
        test = plan["tests"][0]
        test["setup_steps"] = [test["steps"].pop(0)]
        self.assertTrue(validate_plan(plan)["supported"])

    def test_unknown_summary_keys_and_nonfinite_values_rejected(self):
        for record in [{"step":2,"value":1,"path":"score"},{"step":2,"value":float('nan')}]:
            plan = basis_plan()
            plan["tests"][0]["evidence"]["expected_observations"] = [record]
            with self.subTest(record=record),self.assertRaises(ValueError):
                validate_plan(plan)

    def test_summary_does_not_prove_rule_correctness(self):
        plan = basis_plan(99)
        plan["tests"][0]["steps"][-1]["value"] = 99
        self.assertTrue(validate_plan(plan)["supported"])

    def test_legacy_plan_remains_compatible(self):
        self.assertTrue(validate_plan(example_plan())["supported"])

    def test_recovery_cannot_change_frozen_assertion_and_summary_together(self):
        old = basis_plan()
        changed = basis_plan(2)
        changed["tests"][0]["steps"][-1]["value"] = 2
        with self.assertRaisesRegex(ValueError,"assertion"):
            validate_recovery(old,changed)

    def test_known_workshop_mismatch_is_detectable_with_structured_basis(self):
        path = Path(__file__).resolve().parent.parent / "RELIABILITY_RESULTS.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        failed = next(c for c in data["cases"] if c["case_id"]=="charge_exchange")["after"]["self_failures"][0]["test"]
        test = deepcopy(failed)
        test["requirement_ids"] = ["R1"]
        literal = [(i,s) for i,s in enumerate(test["steps"],1) if s["action"]=="assert" and "value" in s]
        test["evidence"]["expected_observations"] = [{"step":i,"value":3 if i==5 else s["value"]} for i,s in literal]
        plan = example_plan()
        plan["tests"] = [test]
        with self.assertRaisesRegex(ValueError,"disagrees"):
            validate_plan(plan)


class FormContractTests(unittest.TestCase):
    def test_fill_empty_and_select_accepted(self):
        steps = [{"action":"fill","selector":"#answer","text":""},
                 {"action":"select_option","selector":"#mode","value":"easy"},
                 {"action":"assert","source":"value","selector":"#answer","op":"eq","value":""}]
        self.assertTrue(validate_plan(plan_steps(steps))["supported"])

    def test_unbounded_or_invalid_form_values_rejected(self):
        for step in [{"action":"fill","selector":"#answer","text":"x"*501},
                     {"action":"fill","selector":"#answer","text":False},
                     {"action":"select_option","selector":"#mode","value":""},
                     {"action":"select_option","selector":"#mode","value":["easy"]}]:
            with self.subTest(step=step),self.assertRaises(ValueError):
                validate_plan(plan_steps([step,example_plan()["tests"][0]["steps"][-1]]))

    def test_form_input_then_rule_assertion_is_functional(self):
        plan = plan_steps([{"action":"fill","selector":"#answer","text":"BLUE"},
                           {"action":"assert","source":"state","path":"score","op":"eq","value":1}])
        self.assertEqual(review_plan(validate_plan(plan))["functional_test_ids"],["T1"])

    def test_input_echo_alone_is_not_functional_evidence(self):
        plan = plan_steps([{"action":"fill","selector":"#answer","text":"BLUE"},
                           {"action":"assert","source":"value","selector":"#answer","op":"eq","value":"BLUE"}])
        self.assertEqual(review_plan(validate_plan(plan))["functional_test_ids"],[])


class DashboardTests(TempTest):
    def serve(self):
        server = make_dashboard_server(self.root,0)
        thread = threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(thread.join,2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_port}"

    def get(self,url):
        with urllib.request.urlopen(url,timeout=4) as response:
            return response.read().decode("utf-8")

    def test_no_evidence_is_unverified(self):
        self.assertEqual(snapshot(self.root)["status"],"unverified")

    def test_failure_is_not_shown_as_success(self):
        (self.root/"summary.json").write_text(json.dumps({"status":"checks_failed"}),encoding="utf-8")
        self.assertIn("Checks failed",render_dashboard(self.root))

    def test_partial_summary_is_unverified(self):
        (self.root/"summary.json").write_text('{"status":',encoding="utf-8")
        self.assertEqual(snapshot(self.root)["status"],"unverified")

    def test_render_escapes_model_supplied_text(self):
        (self.root/"summary.json").write_text(json.dumps({"status":"<script>bad()</script>",
            "requirements":[{"id":"R1","text":"<img src=x onerror=bad()>","status":"not_passed"}]}),encoding="utf-8")
        html = render_dashboard(self.root)
        self.assertNotIn("<script>",html)
        self.assertIn("&lt;img",html)

    def test_only_dashboard_game_and_report_are_served(self):
        write_bundle(example_bundle(),self.root/"game")
        (self.root/"REPORT.md").write_text("Report evidence",encoding="utf-8")
        (self.root/".env").write_text("DO_NOT_SERVE_THIS",encoding="utf-8")
        url = self.serve()
        self.assertIn("PlayForge",self.get(url+"/"))
        self.assertIn("canvas",self.get(url+"/game/"))
        self.assertEqual(self.get(url+"/report"),"Report evidence")
        for path in ["/.env","/summary.json","/traces/api/001_request.json","/game/%2e%2e/.env"]:
            with self.subTest(path=path),self.assertRaises(urllib.error.HTTPError):
                self.get(url+path)

    def test_dashboard_has_no_mutating_endpoint(self):
        url = self.serve()
        with self.assertRaises(urllib.error.HTTPError):
            urllib.request.urlopen(urllib.request.Request(url+"/",data=b"{}",method="POST"),timeout=4)


@unittest.skipUnless(os.getenv("MVP_BROWSER_TESTS")=="1","Opt-in real browser; zero API")
class FormBrowserTests(TempTest):
    def check(self,extra,steps):
        game = self.root/"game"
        write_bundle(example_bundle(extra=extra),game)
        plan = self.root/"plan.json"
        plan.write_text(json.dumps(validate_plan(plan_steps(steps))),encoding="utf-8")
        return verify(game,plan,self.root/"evidence",timeout=25)

    def test_fill_triggers_real_input_and_can_clear(self):
        extra = "const a=document.createElement('input');a.id='answer';document.body.append(a);a.oninput=()=>{score=a.value==='BLUE'?1:0};"
        result = self.check(extra,[{"action":"fill","selector":"#answer","text":"BLUE"},
            {"action":"assert","source":"state","path":"score","op":"eq","value":1},
            {"action":"fill","selector":"#answer","text":""},
            {"action":"assert","source":"value","selector":"#answer","op":"eq","value":""}])
        self.assertTrue(result["ok"],result)

    def test_select_triggers_real_change_event(self):
        extra = "const a=document.createElement('select');a.id='mode';a.innerHTML='<option value=easy>Easy</option><option value=hard>Hard</option>';document.body.append(a);a.onchange=()=>{score=a.value==='hard'?2:1};"
        result = self.check(extra,[{"action":"select_option","selector":"#mode","value":"hard"},
            {"action":"assert","source":"state","path":"score","op":"eq","value":2},
            {"action":"assert","source":"value","selector":"#mode","op":"eq","value":"hard"}])
        self.assertTrue(result["ok"],result)

    def test_password_input_is_blocked(self):
        extra = "const a=document.createElement('input');a.id='answer';a.type='password';document.body.append(a);"
        result = self.check(extra,[{"action":"fill","selector":"#answer","text":"not-a-secret"},
            {"action":"assert","source":"state","path":"score","op":"eq","value":0}])
        self.assertFalse(result["ok"])
        self.assertIn("never password",result["tests"][0]["error"])

    def test_file_input_is_blocked(self):
        extra = "const a=document.createElement('input');a.id='answer';a.type='file';document.body.append(a);"
        result = self.check(extra,[{"action":"fill","selector":"#answer","text":"test.txt"},
            {"action":"assert","source":"state","path":"score","op":"eq","value":0}])
        self.assertFalse(result["ok"])
        self.assertIn("never password",result["tests"][0]["error"])

    def test_readonly_input_is_noop_not_forced(self):
        extra = "const a=document.createElement('input');a.id='answer';a.readOnly=true;a.value='locked';document.body.append(a);"
        result = self.check(extra,[{"action":"fill","selector":"#answer","text":"BLUE"},
            {"action":"assert","source":"value","selector":"#answer","op":"eq","value":"locked"}])
        self.assertTrue(result["ok"],result)

    def test_native_select_disabled_is_noop(self):
        extra = "const a=document.createElement('select');a.id='mode';a.innerHTML='<option value=easy>Easy</option><option value=hard>Hard</option>';a.disabled=true;document.body.append(a);"
        result = self.check(extra,[{"action":"select_option","selector":"#mode","value":"hard"},
            {"action":"assert","source":"value","selector":"#mode","op":"eq","value":"easy"}])
        self.assertTrue(result["ok"],result)


@unittest.skipUnless(os.getenv("MVP_BROWSER_TESTS")=="1","Opt-in real browser; zero API")
class DashboardBrowserTests(TempTest):
    def test_mobile_layout_and_game_link(self):
        from playwright.sync_api import sync_playwright
        write_bundle(example_bundle(),self.root/"game")
        (self.root/"summary.json").write_text(json.dumps({"status":"plan_review_required",
            "requirements":[{"id":"R1","text":"x"*120,"status":"not_passed"}]}),encoding="utf-8")
        server = make_dashboard_server(self.root,0)
        thread = threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(channel=os.getenv("PLAYWRIGHT_CHANNEL") or None)
                try:
                    page = browser.new_page(viewport={"width":390,"height":844})
                    page.goto(f"http://127.0.0.1:{server.server_port}/")
                    self.assertIn("Plan review required",page.locator('[role="status"]').inner_text())
                    self.assertEqual(page.locator('a[href="/game/"]').count(),1)
                    self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
                finally:
                    browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)


if __name__=="__main__":
    unittest.main()
