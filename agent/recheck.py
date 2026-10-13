"""Read-only game replay against an explicit plan; never calls a model."""
import hashlib
import json
from pathlib import Path
import time

from . import __version__
from .contracts import plan_warnings, validate_plan
from .runner import apply_gate, requirement_results
from .verification import failure_summary, verify, verify_repeated
from .evidence import file_hashes


def recheck(game, plan_path, output, timeout=60, headful=False, verifier=verify, repeats=1):
    game, plan_path, output = (Path(p).resolve() for p in (game, plan_path, output))
    if not (game / "index.html").is_file():
        raise ValueError("Game directory must contain index.html")
    if output.exists() or output == game or game in output.parents:
        raise ValueError("Recheck output must be a NEW directory outside the game")
    plan_bytes = plan_path.read_bytes()
    plan = validate_plan(json.loads(plan_bytes.decode("utf-8-sig")))
    if not plan["supported"]:
        raise ValueError("Cannot replay an unsupported plan")
    if not 10 <= timeout <= 180:
        raise ValueError("Recheck timeout must be 10..180 seconds")
    if type(repeats) is not int or not 1 <= repeats <= 3:
        raise ValueError("Recheck repeats must be 1..3")
    files = sorted(p for p in game.rglob("*") if p.is_file())
    hashes = {p.relative_to(game).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    output.mkdir(parents=True, exist_ok=False)
    (output / "plan.json").write_bytes(plan_bytes)
    started = time.monotonic()
    result = verify_repeated(game, output / "plan.json", output / "evidence", timeout=timeout,
                             headful=headful, repeats=repeats, verifier=verifier)
    integrity = (output / "plan.json").read_bytes() == plan_bytes and file_hashes(game) == hashes
    if not integrity:
        result = {**result, "ok": False, "infrastructure_error": "Source/plan changed during read-only replay"}
    result = apply_gate(plan, result, "valid")
    report = {"kind": "offline_recheck", "agent_version": __version__, "api_calls": 0,
              "original_run_success_unchanged": True,
              "game_path": str(game), "source_plan": str(plan_path),
              "plan_sha256": hashlib.sha256(plan_bytes).hexdigest(), "game_sha256": hashes,
              "duration_seconds": round(time.monotonic() - started, 3),
              "verification_repeats": repeats,
              "read_only_integrity": integrity,
              "automated_checks_passed": bool(result.get("ok")), "full_game_acceptance": None,
              "failure_summary": failure_summary(result), "plan_warnings": plan_warnings(plan),
              "requirements": requirement_results(plan, result), "verification": result}
    (output / "recheck.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 独立复测报告", "", "本次不调用模型、不改写游戏，不替代原始自主开发成绩。", "",
             f"- Agent：{__version__}", f"- 自动检查全部通过：{report['automated_checks_passed']}",
             f"- 用时：{report['duration_seconds']} 秒", "- API 调用：0", "",
             "## 需求结果", ""]
    for req in report["requirements"]:
        lines.append(f"- {req['id']} [{req['status']}] {req['text']}")
    lines += ["", "## 诊断", "", json.dumps(report["failure_summary"], ensure_ascii=False, indent=2), "",
              "截图与逐步观察保存在 evidence/ 和 recheck.json。游戏状态接口仍需人工核对真实性。",
              "更换测试计划后的复测通过，不代表原来那次运行自主成功；不要混入 summarize 的成功率。"]
    (output / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if result.get("ok") else 2
