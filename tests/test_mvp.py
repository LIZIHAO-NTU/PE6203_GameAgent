"""No real model calls. Browser tests are opt-in; see README for the distinction."""
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

from agent.config import Config, load_dotenv
from agent.contracts import compare, safe_relative_path, validate_plan, write_bundle
from agent.evaluation import aggregate, export
from agent.provider import BudgetError, ChatClient, ProviderError, parse_json_object
from agent.runner import run
from agent.server import running_server
from agent.trace import Trace
from agent.verification import child_environment, verify, preflight


def example_plan():
    # Synthetic counter UI, deliberately not a prewritten game or game engine.
    return {"supported": True, "reason": "", "title": "Synthetic test page",
            "development_plan": ["Create test page"], "state_contract": {"score": "number"},
            "requirements": [{"id": "R1", "text": "Click increases counter", "verification": "automated"}],
            "tests": [{"id": "T1", "requirement_ids": ["R1"], "description": "Counter click", "steps": [
                {"action": "assert", "source": "state", "path": "score", "op": "eq", "value": 0},
                {"action": "click", "selector": "#increment"},
                {"action": "assert", "source": "state", "path": "score", "op": "eq", "value": 1}]}],
            "manual_checks": []}


def example_bundle(working=True, extra=""):
    return {"summary": "Synthetic UI fixture only", "files": [{"path": "index.html", "content":
        '<!doctype html><html><head><meta charset="utf-8"><title>Test fixture</title></head><body>'
        '<canvas width="200" height="120"></canvas><button id="increment">Increment</button>'
        '<script>let score=0; const c=document.querySelector("canvas").getContext("2d");'
        'c.fillStyle="blue";c.fillRect(10,10,60,60);'
        'window.__gameTest={getState:()=>({score})};'
        'document.querySelector("#increment").onclick=()=>{' + ('score++;' if working else '') + '};'
        + extra + '</script></body></html>'}]}


def config():
    return Config("test-key-never-real", "https://api.deepseek.com", "test-model", "", True,
                  4000, 20, None, None, None, "USD")


def verifier_result(passed):
    return {"ok": passed, "smoke": {"passed": True}, "tests": [{"id": "T1", "passed": passed}],
            "runtime_errors": [], "infrastructure_error": None}


class TempTest(unittest.TestCase):
    def setUp(self):
        base = Path(os.environ.get("MVP_TEST_TMP", ".codex-tmp")).resolve()
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)


class ContractTests(TempTest):
    def test_valid_plan(self):
        self.assertTrue(validate_plan(example_plan())["supported"])

    def test_rejects_unsafe_paths(self):
        for value in ["../.env", "/index.html", "C:/x.js", "a\\b.js", "CON.js", "aux/x.js",
                      "file.py", ".env", "foo//bar.js", "foo/./bar.js", "a./b.js"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                safe_relative_path(value)

    def test_rejects_duplicates_before_writing(self):
        bundle = example_bundle()
        bundle["files"].append({"path": "INDEX.html", "content": "bad"})
        target = self.root / "game"
        with self.assertRaises(ValueError):
            write_bundle(bundle, target)
        self.assertFalse(target.exists())

    def test_missing_entry_rejected(self):
        with self.assertRaises(ValueError):
            write_bundle({"files": [{"path": "a.js", "content": "x"}]}, self.root / "game")

    def test_no_overwrite(self):
        target = self.root / "game"
        write_bundle(example_bundle(), target)
        with self.assertRaises(ValueError):
            write_bundle(example_bundle(False), target)

    def test_bad_tests_rejected(self):
        for modify in [lambda p: p["tests"][0]["steps"].clear(),
                       lambda p: p["tests"][0].update(requirement_ids=["unknown"]),
                       lambda p: p["tests"][0]["steps"][0].update(action="execute_python")]:
            plan = example_plan()
            modify(plan)
            with self.assertRaises(ValueError):
                validate_plan(plan)

    def test_manual_requirements_need_checklist(self):
        plan = example_plan()
        plan["requirements"].append({"id": "R2", "text": "Artwork", "verification": "manual"})
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_capture_before_use_and_numeric_checks(self):
        self.assertFalse(compare(True, "eq", 1))
        self.assertTrue(compare(1, "eq", 1.0))
        with self.assertRaises(ValueError):
            compare("3", "gt", 2)
        plan = example_plan()
        plan["tests"][0]["steps"][0].pop("value")
        plan["tests"][0]["steps"][0]["value_from"] = {"capture": "missing", "path": "score"}
        with self.assertRaises(ValueError):
            validate_plan(plan)


class ConfigurationTests(TempTest):
    def test_env_is_data_not_code(self):
        env = self.root / "env"
        env.write_text('MVP_SAMPLE="hello"\nMVP_OTHER=$(not_executed)\n', encoding="utf-8")
        with patch.dict(os.environ, {"MVP_SAMPLE": "existing"}, clear=True):
            load_dotenv(env)
            self.assertEqual(os.environ["MVP_SAMPLE"], "existing")
            self.assertEqual(os.environ["MVP_OTHER"], "$(not_executed)")

    def test_rejects_unsafe_api_url(self):
        for url in ["http://example.com", "https://key@example.com", "https://api.example.com?token=x"]:
            with patch.dict(os.environ, {"LLM_BASE_URL": url}, clear=True), self.assertRaises(ValueError):
                Config.from_env()

    def test_child_strips_secrets(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "secret", "MY_TOKEN": "secret", "PATH": "ok",
                                   "MVP_TEST_TMP": str(self.root)}, clear=True):
            env = child_environment()
            self.assertNotIn("DEEPSEEK_API_KEY", env)
            self.assertNotIn("MY_TOKEN", env)
            self.assertEqual(env["PATH"], "ok")

    def test_trace_redacts(self):
        trace = Trace(self.root / "traces", ("real-secret",))
        trace.save("x.json", {"text": "real-secret"})
        trace.event("test", value="real-secret")
        for file in trace.root.iterdir():
            self.assertNotIn("real-secret", file.read_text(encoding="utf-8"))


class ProviderTests(TempTest):
    def client(self, limit=8):
        import time
        return ChatClient(config(), Trace(self.root / "trace", (config().api_key,)), limit, time.monotonic() + 60)

    def test_json_object_only(self):
        self.assertEqual(parse_json_object('```json\n{"ok":true}\n```'), {"ok": True})
        for text in ["[]", "", '{"x":NaN}']:
            with self.assertRaises((ValueError, json.JSONDecodeError)):
                parse_json_object(text)

    def test_usage_from_http_response(self):
        body = {"choices": [{"message": {"content": '{"ok":true}'}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20, "prompt_cache_hit_tokens": 30}}
        with patch("agent.provider.open_request", return_value=io.BytesIO(json.dumps(body).encode())):
            client = self.client()
            self.assertTrue(client.ask_json("plan", "Return JSON", "test")["ok"])
        self.assertEqual(client.prompt_tokens, 100)
        self.assertEqual(client.completion_tokens, 20)
        self.assertEqual(client.cached_tokens, 30)
        self.assertIsNone(client.usage_summary()["estimated_known_usage_cost"])

    def test_auth_failure_not_retried(self):
        error = urllib.error.HTTPError("https://example.com", 401, "Unauthorized", {}, None)
        client = self.client()
        with patch("agent.provider.open_request", side_effect=error), self.assertRaises(ProviderError):
            client.ask_json("plan", "json", "test")
        self.assertEqual(client.calls, 1)

    def test_request_budget_enforced(self):
        with self.assertRaises(BudgetError):
            self.client(0).ask_json("plan", "json", "test")

    def test_cost_uses_configured_cache_rates(self):
        import time
        cfg = replace(config(), input_price=2, cached_price=.5, output_price=4)
        client = ChatClient(cfg, Trace(self.root / "trace"), 8, time.monotonic() + 60)
        client.prompt_tokens, client.cached_tokens, client.completion_tokens = 1000, 400, 100
        self.assertAlmostEqual(client.usage_summary()["estimated_known_usage_cost"], .0018)
        self.assertTrue(client.usage_summary()["cost_is_complete"])

    def test_redirects_do_not_forward_key(self):
        from agent.provider import NoRedirect
        request = urllib.request.Request("https://api.example.com", headers={"Authorization": "Bearer secret"})
        self.assertIsNone(NoRedirect().redirect_request(request, None, 302, "Found", {}, "https://other.example.com"))

    def test_truncated_output_is_not_success(self):
        body = {"choices": [{"message": {"content": '{"ok":true}'}, "finish_reason": "length"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20}}
        client = self.client(1)
        with patch("agent.provider.open_request", return_value=io.BytesIO(json.dumps(body).encode())), \
             patch("agent.provider.time.sleep"), self.assertRaises(BudgetError):
            client.ask_json("plan", "json", "test")
        self.assertEqual(client.prompt_tokens, 10)


class FakeClient:
    def __init__(self, cfg, trace, max_calls, deadline):
        self.calls = 0

    def ask_json(self, stage, system, prompt):
        self.calls += 1
        if stage == "plan":
            return example_plan()
        return example_bundle(working=self.calls >= 3)

    def usage_summary(self):
        return {"api_attempts": self.calls, "prompt_tokens": 0, "completion_tokens": 0,
                "calls_with_unknown_usage": 0, "cached_input_tokens": 0,
                "estimated_known_usage_cost": None, "currency": "USD", "cost_is_complete": False}


class ControllerTests(TempTest):
    def invoke(self, **options):
        spec = self.root / "spec.md"
        spec.write_text("Synthetic counter fixture, not a game", encoding="utf-8")
        output = self.root / "run"
        code = run(config(), spec, output, client_factory=FakeClient,
                   preflight_fn=lambda **kw: {"ok": True}, **options)
        return code, output, json.loads((output / "summary.json").read_text(encoding="utf-8"))

    def test_failure_repair_success(self):
        def check(game, *args, **kwargs):
            return verifier_result("score++;" in (game / "index.html").read_text(encoding="utf-8"))
        code, output, summary = self.invoke(verifier=check)
        self.assertEqual(code, 0)
        self.assertTrue(summary["recovered_after_verification_failure"])
        self.assertIsNone(summary["full_game_acceptance"])
        self.assertEqual(summary["selected_round"], 2)
        self.assertTrue((output / "game" / "index.html").is_file())
        self.assertTrue((output / "traces" / "plan.json").is_file())
        self.assertEqual(summary["requirements"][0]["status"], "automated_pass")

    def test_bounded_failure_is_not_success(self):
        code, output, summary = self.invoke(verifier=lambda *a, **k: verifier_result(False), max_rounds=2)
        self.assertEqual(code, 2)
        self.assertFalse(summary["automated_checks_passed"])
        self.assertEqual(len(summary["attempts"]), 2)

    def test_best_version_preserved_on_later_regression(self):
        calls = []
        def check(*args, **kwargs):
            calls.append(1)
            result = verifier_result(False)
            result["smoke"]["passed"] = len(calls) == 1
            return result
        _, _, summary = self.invoke(verifier=check, max_rounds=2)
        self.assertEqual(summary["selected_round"], 1)

    def test_unsupported_spec_not_substituted(self):
        class UnsupportedClient(FakeClient):
            def ask_json(self, *args):
                return {"supported": False, "reason": "Requires native 3D engine"}
        spec = self.root / "spec.md"
        spec.write_text("Requires native 3D engine", encoding="utf-8")
        code = run(config(), spec, self.root / "run", client_factory=UnsupportedClient,
                   preflight_fn=lambda **kw: {"ok": True})
        self.assertEqual(code, 3)
        self.assertFalse((self.root / "run" / "game").exists())

    def test_no_existing_output_overwrite(self):
        spec = self.root / "spec.md"
        spec.write_text("x", encoding="utf-8")
        with self.assertRaises(ValueError):
            run(config(), spec, self.root)

    def test_budget_failure_preserves_existing_candidate(self):
        class LimitedClient(FakeClient):
            def ask_json(self, *args):
                if self.calls >= 2:
                    raise BudgetError("Simulated API budget reached")
                return super().ask_json(*args)
        spec = self.root / "spec.md"
        spec.write_text("Synthetic fixture", encoding="utf-8")
        output = self.root / "run"
        code = run(config(), spec, output, client_factory=LimitedClient,
                   preflight_fn=lambda **kw: {"ok": True}, verifier=lambda *a, **k: verifier_result(False))
        summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(code, 4)
        self.assertEqual(summary["status"], "budget_exhausted")
        self.assertTrue((output / "game" / "index.html").exists())

    def test_interrupt_reported_not_success(self):
        def interrupt(*args, **kwargs):
            raise KeyboardInterrupt()
        _, _, summary = self.invoke(verifier=interrupt)
        self.assertEqual(summary["status"], "interrupted")
        self.assertFalse(summary["automated_checks_passed"])

    def test_aggregate_denominators_and_export(self):
        parent = self.root / "runs"
        for i, success in enumerate([True, False]):
            path = parent / str(i)
            path.mkdir(parents=True)
            (path / "summary.json").write_text(json.dumps({"schema_version": 1, "run_id": str(i),
                "status": "test", "automated_checks_passed": success, "duration_seconds": 1}), encoding="utf-8")
        report = aggregate(parent)
        self.assertEqual(report["metrics"]["automated_check_success_rate_over_all_runs"], .5)
        self.assertIsNone(report["metrics"]["recovery_success_rate"])
        out = self.root / "report.json"
        export(parent, out)
        self.assertTrue(out.with_suffix(".csv").exists())
        with self.assertRaises(ValueError):
            export(parent, out)


class ServerTests(TempTest):
    def test_serves_only_local_game_files(self):
        game = self.root / "game"
        write_bundle(example_bundle(), game)
        (self.root / "secret.txt").write_text("private", encoding="utf-8")
        with running_server(game) as origin:
            with urllib.request.urlopen(origin + "/") as response:
                self.assertIn("connect-src 'none'", response.headers["Content-Security-Policy"])
                self.assertIn(b"Test fixture", response.read())
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(origin + "/%2e%2e/secret.txt")


@unittest.skipUnless(os.getenv("MVP_BROWSER_TESTS") == "1", "Opt-in real browser; no API calls")
class BrowserIntegrationTests(TempTest):
    def test_http_provider_to_real_browser_full_loop(self):
        requests = []
        class MockAPI(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append(request)
                content = example_plan() if len(requests) == 1 else example_bundle(len(requests) >= 3)
                body = json.dumps({"choices": [{"message": {"content": json.dumps(content)},
                                                "finish_reason": "stop"}],
                                   "usage": {"prompt_tokens": 100, "completion_tokens": 50}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        server = ThreadingHTTPServer(("127.0.0.1", 0), MockAPI)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            cfg = replace(config(), base_url=f"http://127.0.0.1:{server.server_port}")
            spec = self.root / "spec.md"
            spec.write_text("Synthetic fixture only", encoding="utf-8")
            output = self.root / "run"
            code = run(cfg, spec, output, max_rounds=2)
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(code, 0)
            self.assertEqual(len(requests), 3)
            self.assertEqual(summary["usage"]["prompt_tokens"], 300)
            self.assertTrue(summary["recovered_after_verification_failure"])
            for path in (output / "traces").rglob("*.json"):
                self.assertNotIn(config().api_key, path.read_text(encoding="utf-8"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_browser_detects_logic_failure_then_repair(self):
        plan_path = self.root / "plan.json"
        plan_path.write_text(json.dumps(example_plan()), encoding="utf-8")
        for working in [False, True]:
            game = self.root / str(working) / "game"
            write_bundle(example_bundle(working), game)
            result = verify(game, plan_path, game.parent / "evidence", timeout=30)
            self.assertIsNone(result.get("infrastructure_error"), result)
            self.assertEqual(result["ok"], working, result)

    def test_real_browser_controller_repair_loop(self):
        spec = self.root / "spec.md"
        spec.write_text("Synthetic counter fixture", encoding="utf-8")
        code = run(config(), spec, self.root / "run", max_rounds=2,
                   client_factory=FakeClient, verifier=verify, preflight_fn=preflight)
        self.assertEqual(code, 0)
        summary = json.loads((self.root / "run" / "summary.json").read_text(encoding="utf-8"))
        self.assertTrue(summary["recovered_after_verification_failure"])

    def test_browser_detects_runtime_error(self):
        game = self.root / "game"
        write_bundle(example_bundle(extra='throw new Error("deliberate runtime error");'), game)
        plan_path = self.root / "plan.json"
        plan_path.write_text(json.dumps(example_plan()), encoding="utf-8")
        result = verify(game, plan_path, self.root / "evidence", timeout=30)
        self.assertFalse(result["ok"])
        self.assertTrue(result["runtime_errors"], result)

    def test_hanging_state_hook_hits_worker_timeout(self):
        game = self.root / "game"
        write_bundle(example_bundle(extra='window.__gameTest.getState=()=>{while(true){}};'), game)
        plan_path = self.root / "plan.json"
        plan_path.write_text(json.dumps(example_plan()), encoding="utf-8")
        result = verify(game, plan_path, self.root / "evidence", timeout=4)
        self.assertFalse(result["ok"])
        self.assertIn("time budget", result.get("infrastructure_error", ""))


if __name__ == "__main__":
    unittest.main()
