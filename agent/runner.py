"""Controller-owned planning -> generation -> verification -> bounded repair loop."""
import hashlib
import json
from pathlib import Path
import shutil
import time

from . import __version__
from .contracts import plan_warnings, validate_plan, write_bundle
from .prompts import CODER_SYSTEM, PLANNER_SYSTEM
from .provider import BudgetError, ChatClient
from .trace import Trace
from .verification import failure_summary, preflight, verify


def verification_score(result):
    return (bool(result.get("ok")), bool(result.get("smoke", {}).get("passed")),
            sum(bool(t.get("passed")) for t in result.get("tests", [])),
            not bool(result.get("runtime_errors")))


def requirement_results(plan, result):
    results = {t["id"]: t for t in result.get("tests", [])}
    records = []
    for requirement in plan.get("requirements", []):
        related = [t["id"] for t in plan["tests"] if requirement["id"] in t["requirement_ids"]]
        checked = bool(related) and all(results.get(t, {}).get("passed", False) for t in related)
        records.append({**requirement, "test_ids": related,
                        "status": "automated_pass" if checked else
                        ("manual_pending" if requirement["verification"] == "manual" else "not_passed")})
    return records


def run(config, spec_path, output, max_rounds=3, max_calls=8, max_seconds=600,
        test_timeout=60, headful=False, client_factory=ChatClient, verifier=verify,
        preflight_fn=preflight):
    started = time.monotonic()
    deadline = started + max_seconds
    if spec_path.suffix.lower() != ".md":
        raise ValueError("Specification input must be a Markdown .md file")
    spec = spec_path.read_text(encoding="utf-8-sig")
    if not spec.strip() or len(spec.encode("utf-8")) > 30000:
        raise ValueError("Specification must be nonempty and <=30 KB")
    if not config.api_key:
        raise ValueError("No API key: configure DEEPSEEK_API_KEY in .env or your environment")
    if config.api_key in spec:
        raise ValueError("Configured API key appears in the specification; remove it before sending")
    if output.exists():
        raise ValueError("Output already exists; choose a new path (no runs are overwritten)")
    print("[1/4] Checking local browser; no API credits used yet...", flush=True)
    check = preflight_fn(timeout=min(25, max_seconds))
    if not check.get("ok"):
        raise RuntimeError("Browser unavailable. Install requirements and Chromium, then run doctor.\n"
                           + str(check.get("infrastructure_error", "Unknown browser error")))
    output.mkdir(parents=True, exist_ok=False)
    trace = Trace(output / "traces", (config.api_key,))
    trace.save("original_spec.json", {"filename": spec_path.name, "content": spec})
    client = client_factory(config, trace, max_calls, deadline)
    summary = {"schema_version": 1, "agent_version": __version__, "run_id": output.name, "model": config.model,
               "original_spec_sha256": hashlib.sha256(spec.encode("utf-8")).hexdigest(),
               "prompts_sha256": hashlib.sha256((PLANNER_SYSTEM + CODER_SYSTEM).encode("utf-8")).hexdigest(),
               "limits": {"max_rounds": max_rounds, "max_calls": max_calls,
                          "max_seconds": max_seconds, "test_timeout": test_timeout},
               "base_url": config.base_url, "status": "started", "automated_checks_passed": False,
               "full_game_acceptance": None, "manual_interventions_during_run": 0,
               "first_playable_seconds": None, "had_verification_failure": False,
               "recovered_after_verification_failure": False, "attempts": [],
               "limitations": ["Vanilla offline 2D browser games only; not the full course scope.",
                   "Tests and implementation use the same model; shared blind spots remain.",
                   "State hooks are game-supplied observations, not independent proof.",
                   "Browser/network restrictions are defense in depth, not a hardened OS sandbox.",
                   "Automated checks passed does not mean full gameplay acceptance."]}
    plan, best, previous, feedback = None, None, None, None
    exit_code = 4
    try:
        trace.event("run_start", model=config.model, max_rounds=max_rounds,
                    max_calls=max_calls, max_seconds=max_seconds, browser=check)
        print("[2/4] Planning requirements and frozen acceptance tests...", flush=True)
        plan_error = None
        for _ in range(2):
            prompt = json.dumps({"original_spec": spec, "validation_feedback": plan_error}, ensure_ascii=False)
            raw_plan = client.ask_json("plan", PLANNER_SYSTEM, prompt)
            try:
                plan = validate_plan(raw_plan)
                break
            except (ValueError, TypeError, KeyError) as error:
                plan_error = str(error)
                trace.event("plan_validation_failed", error=plan_error)
        else:
            raise ValueError("Could not produce a valid test plan: " + str(plan_error))
        trace.save("plan.json", plan)
        plan_path = trace.root / "plan.json"
        plan_bytes = plan_path.read_bytes()
        plan_hash = hashlib.sha256(plan_bytes).hexdigest()
        summary["plan_sha256"] = plan_hash
        summary["plan_warnings"] = plan_warnings(plan)
        trace.save("plan_review.json", {"warnings": summary["plan_warnings"],
                   "note": "Heuristic warnings only; not a complete semantic audit."})
        if not plan["supported"]:
            summary.update(status="unsupported_spec", error=plan["reason"])
            exit_code = 3
        else:
            for round_number in range(1, max_rounds + 1):
                if time.monotonic() >= deadline:
                    raise BudgetError("Run time budget reached")
                print(f"[3/4] Generation / repair {round_number}/{max_rounds}...", flush=True)
                prompt = json.dumps({"original_spec": spec, "frozen_plan": plan,
                    "previous_version": previous, "verification_feedback": feedback}, ensure_ascii=False)
                bundle = client.ask_json(f"code_{round_number}", CODER_SYSTEM, prompt)
                attempt_dir = trace.root / "attempts" / f"{round_number:02d}"
                candidate = attempt_dir / "game"
                try:
                    write_bundle(bundle, candidate)
                except (ValueError, OSError, TypeError) as error:
                    feedback = {"bundle_validation_error": str(error)}
                    summary["attempts"].append({"round": round_number, "bundle_valid": False, **feedback})
                    trace.event("bundle_rejected", round=round_number, **feedback)
                    continue
                previous = bundle
                if plan_path.read_bytes() != plan_bytes:
                    raise RuntimeError("Frozen plan changed unexpectedly; aborting")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    # Preserve valid generated source, but never call it tested.
                    result = {"ok": False, "smoke": {"passed": False}, "tests": [],
                              "infrastructure_error": "Time budget exhausted before verification"}
                else:
                    print("      Running browser smoke + interaction tests...", flush=True)
                    result = verifier(candidate, plan_path, attempt_dir / "evidence",
                                      timeout=min(test_timeout, remaining), headful=headful)
                trace.save(f"attempts/{round_number:02d}/verification.json", result)
                elapsed = round(time.monotonic() - started, 3)
                if result.get("smoke", {}).get("passed") and summary["first_playable_seconds"] is None:
                    # A first visible version, not a guarantee of full playability.
                    summary["first_playable_seconds"] = elapsed
                entry = {"round": round_number, "bundle_valid": True,
                         "failure_summary": failure_summary(result),
                         "automated_checks_passed": bool(result.get("ok")),
                         "smoke_passed": bool(result.get("smoke", {}).get("passed")),
                         "tests_passed": sum(bool(t.get("passed")) for t in result.get("tests", [])),
                         "tests_total": len(plan["tests"]), "elapsed_seconds": elapsed,
                         "infrastructure_error": result.get("infrastructure_error")}
                summary["attempts"].append(entry)
                trace.event("verification", **entry, decision=bundle.get("summary", "")[:2000])
                if best is None or verification_score(result) >= verification_score(best[1]):
                    best = (candidate, result, round_number)
                if result.get("ok"):
                    summary["recovered_after_verification_failure"] = summary["had_verification_failure"]
                    break
                if result.get("infrastructure_error"):
                    # Browser infrastructure failure is not fixed by rewriting game logic.
                    summary["error"] = result["infrastructure_error"]
                    break
                summary["had_verification_failure"] = True
                feedback = result
            if best:
                chosen, result, chosen_round = best
                shutil.copytree(chosen, output / "game")
                summary.update(selected_round=chosen_round,
                               automated_checks_passed=bool(result.get("ok")),
                               smoke_passed=bool(result.get("smoke", {}).get("passed")),
                               requirements=requirement_results(plan, result),
                               manual_checks=plan.get("manual_checks", []))
                summary["failure_summary"] = failure_summary(result)
                reqs = summary["requirements"]
                automated = [r for r in reqs if r["verification"] == "automated"]
                summary["automated_requirement_pass_rate"] = (
                    sum(r["status"] == "automated_pass" for r in automated) / len(automated) if automated else None)
                summary["status"] = "automated_passed_manual_pending" if result.get("ok") else "checks_failed"
                exit_code = 0 if result.get("ok") else 2
            else:
                summary.update(status="generation_failed", error="No valid game bundle produced")
                exit_code = 2
    except (Exception, KeyboardInterrupt) as error:
        status = "interrupted" if isinstance(error, KeyboardInterrupt) else (
            "budget_exhausted" if isinstance(error, BudgetError) else "run_error")
        summary.update(status=status,
                       error=trace.redact(str(error)))
        trace.event("run_error", error=summary["error"])
        if best and not (output / "game").exists():
            shutil.copytree(best[0], output / "game")
            summary.update(selected_round=best[2], smoke_passed=bool(best[1].get("smoke", {}).get("passed")),
                           requirements=requirement_results(plan, best[1]),
                           manual_checks=plan.get("manual_checks", []))
            summary["failure_summary"] = failure_summary(best[1])
        exit_code = 130 if isinstance(error, KeyboardInterrupt) else 4
    finally:
        summary["duration_seconds"] = round(time.monotonic() - started, 3)
        summary["usage"] = client.usage_summary()
        summary["first_playable_metric_note"] = "Time to first visible smoke-passing version; not full acceptance."
        trace.event("run_end", status=summary["status"], duration_seconds=summary["duration_seconds"])
        trace.save("summary.json", summary)
        (output / "summary.json").write_text(trace.redact(json.dumps(summary, ensure_ascii=False, indent=2)), encoding="utf-8")
        write_report(output, summary)
        print(f"[4/4] {summary['status']}\nResults: {output.resolve()}", flush=True)
        if (output / "game").is_dir():
            print(f'Play: python -m agent serve "{output.resolve() / "game"}"', flush=True)
    return exit_code


def write_report(output, summary):
    usage = summary["usage"]
    lines = ["# 自动开发运行报告", "", f"- 状态：`{summary['status']}`",
             f"- 模型：`{summary['model']}`", f"- 耗时：{summary['duration_seconds']} 秒",
             f"- API 尝试次数：{usage['api_attempts']}",
             f"- 已知输入 / 输出 token：{usage['prompt_tokens']} / {usage['completion_tokens']}",
             f"- 用量未知的调用次数：{usage['calls_with_unknown_usage']}",
             f"- 已知用量估算费用：{usage['estimated_known_usage_cost']} {usage['currency']}", "",
             "自动通过不等于完整验收；None 表示未测量或未配置价格，不是零。", "",
             "## 需求与自动检查", ""]
    for item in summary.get("requirements", []):
        lines.append(f"- {item['id']} [{item['status']}] {item['text']}")
    lines += ["", "## 测试诊断与计划提醒", "",
              f"- Agent 版本：{summary.get('agent_version', 'unknown')}",
              f"- 自动需求通过比例：{summary.get('automated_requirement_pass_rate')}",
              f"- 失败分类：{json.dumps(summary.get('failure_summary', {}).get('counts', {}), ensure_ascii=False)}",
              f"- 建议复核的测试：{summary.get('failure_summary', {}).get('review_test_ids', [])}", "",
              "目标超时、断言不符不直接证明游戏代码错误，也可能是操作策略或测试计划问题。失败不会因此自动算通过。"]
    for warning in summary.get("plan_warnings", []):
        lines.append(f"- {warning['test_id']}: {warning['message']}")
    lines += ["", "## 人工试玩待办", "", "- [ ] 根据原始需求完整试玩，检查自动测试遗漏和状态钩子的真实性。"]
    for check in summary.get("manual_checks", []):
        lines.append(f"- [ ] {check['requirement_id']}: {check['instruction']}")
    if summary.get("error"):
        lines += ["", "## 未完成或错误", "", summary["error"]]
    lines += ["", "## 启动游戏", "", "在 MVP 项目目录运行：", "", "```powershell",
              f'python -m agent serve "{output.resolve() / "game"}"', "```", "",
              "原始需求、固定测试计划、API 用量、每轮结果和截图均位于 traces/。", "",
              "计价依赖用户配置；失败/超时请求也可能计费，以服务商账单为准。"]
    (output / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
