"""Cross-mechanic evaluation with held-out checks and a shared API-attempt cap."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import time

from . import __version__
from .contracts import identifier, validate_plan
from .runner import apply_gate, run
from .verification import verify


def load_suite(path):
    path = path.resolve()
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    cases = data.get("cases")
    if not isinstance(cases, list) or not 1 <= len(cases) <= 20:
        raise ValueError("Suite needs 1..20 cases")
    seen, loaded = set(), []
    for case in cases:
        name = identifier(case.get("id"))
        family = identifier(case.get("family"))
        if name in seen:
            raise ValueError("Duplicate benchmark case")
        seen.add(name)
        record = {"id": name, "family": family}
        for key, suffix in (("spec", ".md"), ("acceptance_plan", ".json")):
            relative = case.get(key)
            if not isinstance(relative, str) or Path(relative).is_absolute():
                raise ValueError("Suite paths must be relative")
            source = (path.parent / relative).resolve()
            if not source.is_relative_to(path.parent) or source.suffix.lower() != suffix or not source.is_file():
                raise ValueError("Suite source missing or outside suite directory")
            record[key] = source
            record[key + "_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        acceptance = validate_plan(json.loads(record["acceptance_plan"].read_text(encoding="utf-8")))
        if not acceptance["supported"]:
            raise ValueError("Independent acceptance plan must be supported")
        loaded.append(record)
    return loaded


def metrics(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["family"]].append(row)
    by_family = {}
    for family, group in groups.items():
        by_family[family] = {"scheduled": len(group),
            "attempted": sum(r.get("attempted", False) for r in group),
            "launch_rate": sum(r.get("launch_passed", False) for r in group) / len(group),
            "independent_pass_rate": sum(r.get("independent_passed", False) for r in group) / len(group)}
    return {"scheduled": len(rows), "attempted": sum(r.get("attempted", False) for r in rows),
        "api_attempts": sum(r.get("usage", {}).get("api_attempts", 0) for r in rows),
        "launch_rate": sum(r.get("launch_passed", False) for r in rows) / len(rows) if rows else None,
        "model_plan_pass_rate": sum(r.get("model_plan_passed", False) for r in rows) / len(rows) if rows else None,
        "independent_pass_rate": sum(r.get("independent_passed", False) for r in rows) / len(rows) if rows else None,
        "macro_family_independent_pass_rate":
            sum(g["independent_pass_rate"] for g in by_family.values()) / len(by_family) if by_family else None,
        "prompt_tokens": sum(r.get("usage", {}).get("prompt_tokens", 0) for r in rows),
        "completion_tokens": sum(r.get("usage", {}).get("completion_tokens", 0) for r in rows),
        "calls_with_unknown_usage": sum(r.get("usage", {}).get("calls_with_unknown_usage", 0) for r in rows),
        "by_family": by_family,
        "full_game_acceptance_rate": None,
        "notes": ["Independent checks are held out from generation; they still cover only selected requirements.",
                  "One run per family is a feasibility sample, not a reliable generalization estimate.",
                  "Rates include all scheduled cases, including skipped/error cases; raw rows preserve causes."]}


def save_report(output, report):
    report["metrics"] = metrics(report["cases"])
    (output / "benchmark.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 多玩法测试 / Cross-mechanic benchmark", "",
             f"Agent: {report['agent_version']} · Model: {report['model']}",
             f"API attempts: {report['metrics']['api_attempts']} / {report['max_total_calls']}", "",
             "| Case | Family | Launch | Model plan | Independent checks | Calls | Status |",
             "|---|---|---|---|---|---|---|"]
    for row in report["cases"]:
        checks = f"{row.get('independent_tests_passed', 0)}/{row.get('independent_tests_total', 0)}"
        lines.append(f"| {row['run_id']} | {row['family']} | {row.get('launch_passed', False)} | "
                     f"{row.get('model_plan_passed', False)} | {checks} | "
                     f"{row.get('usage', {}).get('api_attempts', 0)} | {row['status']} |")
    lines += ["", "独立检查未提供给生成模型，不改变原运行成绩；通过仍不等于完整游戏验收。",
              "每类一次仅用于可行性检查，不能据此声称已经稳定泛化。", "",
              "各次生成游戏位于 cases/<run_id>/game；模型计划和修复记录位于该目录的 traces/；",
              "独立检查结果和截图位于 acceptance/<run_id>/。使用 python -m agent serve <game目录> 试玩。"]
    (output / "BENCHMARK.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def benchmark(config, suite_path, output, max_total_calls=20, max_calls_per_case=5,
              max_rounds=3, max_seconds=420, repeats=1, runner=run, verifier=verify):
    if not (1 <= max_total_calls <= 200 and 2 <= max_calls_per_case <= 30 and
            1 <= max_rounds <= 10 and 30 <= max_seconds <= 3600 and 1 <= repeats <= 10):
        raise ValueError("Invalid benchmark budget/repetition limits")
    cases = load_suite(suite_path)  # Validate ALL cases before any paid model call.
    if output.exists():
        raise ValueError("Benchmark output exists; refusing to overwrite")
    output.mkdir(parents=True)
    rows = [{"run_id": f"{case['id']}_{i + 1:02d}", "case_id": case["id"], "family": case["family"],
             "status": "pending", "attempted": False,
             "spec_sha256": case["spec_sha256"], "acceptance_plan_sha256": case["acceptance_plan_sha256"]}
            for i in range(repeats) for case in cases]
    report = {"agent_version": __version__, "model": config.model,
              "max_total_calls": max_total_calls, "max_calls_per_case": max_calls_per_case,
              "max_rounds": max_rounds, "max_seconds_per_case": max_seconds,
              "repeats": repeats, "cases": rows}
    used, halted = 0, False
    try:
        for index, row in enumerate(rows):
            case = cases[index % len(cases)]
            remaining = max_total_calls - used
            if halted or remaining < 2:
                row["status"] = "skipped_budget_or_prior_error"
                continue
            destination = output / "cases" / row["run_id"]
            row.update(attempted=True, status="running")
            save_report(output, report)
            print(f"\nBenchmark {row['run_id']} [{row['family']}], remaining API attempts: {remaining}", flush=True)
            started = time.monotonic()
            # Only the MD spec goes to the agent. The held-out plan is NEVER passed to it.
            exit_code = runner(config, case["spec"], destination, max_rounds=max_rounds,
                               max_calls=min(max_calls_per_case, remaining), max_seconds=max_seconds)
            summary = json.loads((destination / "summary.json").read_text(encoding="utf-8"))
            usage = summary["usage"]
            count = usage["api_attempts"]
            if type(count) is not int or not 0 <= count <= min(max_calls_per_case, remaining):
                raise RuntimeError("Cannot safely account for API attempts; stopping benchmark")
            used += count
            row.update(status=summary["status"], exit_code=exit_code, usage=usage,
                       launch_passed=bool(summary.get("smoke_passed")) and not summary.get("runtime_error_count", 0),
                       model_plan_passed=bool(summary.get("automated_checks_passed")),
                       prompts_sha256=summary.get("prompts_sha256"))
            if (destination / "game" / "index.html").is_file():
                evidence = output / "acceptance" / row["run_id"]
                result = verifier(destination / "game", case["acceptance_plan"], evidence, timeout=60)
                acceptance = validate_plan(json.loads(case["acceptance_plan"].read_text(encoding="utf-8")))
                result = apply_gate(acceptance, result, "valid")
                evidence.mkdir(parents=True, exist_ok=True)
                (evidence / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                row.update(independent_passed=bool(result.get("ok")),
                           independent_tests_passed=sum(t.get("passed", False) for t in result.get("tests", [])),
                           independent_tests_total=len(json.loads(case["acceptance_plan"].read_text(encoding="utf-8"))["tests"]),
                           independent_failure_kinds=[t.get("failure_kind") for t in result.get("tests", []) if not t.get("passed")])
            row["duration_seconds"] = round(time.monotonic() - started, 3)
            # Do not spend more credits repeating a permanent account/configuration failure.
            if summary["status"] == "run_error" and any(
                    f"API HTTP {code}" in summary.get("error", "") for code in (400, 401, 402, 403, 404, 422)):
                halted = True
            save_report(output, report)
    except BaseException:
        for row in rows:
            if row["status"] == "running":
                row["status"] = "benchmark_error_or_interrupted"
                summary_path = output / "cases" / row["run_id"] / "summary.json"
                if summary_path.is_file() and "usage" not in row:
                    row["usage"] = json.loads(summary_path.read_text(encoding="utf-8")).get("usage", {})
        raise
    finally:
        save_report(output, report)
    return report
