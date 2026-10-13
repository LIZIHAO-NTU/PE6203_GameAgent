"""Run trusted verification in a separate process with a hard timeout."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys


def failure_summary(result):
    """Aggregate evidence categories, not diagnoses of who caused the failure."""
    counts, review_ids = {}, []
    for test in result.get("tests", []):
        if not test.get("passed"):
            kind = test.get("failure_kind", "unclassified")
            counts[kind] = counts.get(kind, 0) + 1
            if test.get("needs_test_review"):
                review_ids.append(test["id"])
    return {"counts": counts, "review_test_ids": review_ids,
            "infrastructure_error": result.get("infrastructure_error"),
            "quality_gate": result.get("quality_gate"),
            "note": "A failed test remains failed. Review flags are uncertainty, not proof of a bad test or a correct game."}


def child_environment():
    # The model and generated page never receive credentials. Retain runtime paths.
    sensitive = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "PROXY")
    env = {k: v for k, v in os.environ.items() if not any(word in k.upper() for word in sensitive)}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUTF8"] = "1"
    temporary = Path(os.getenv("MVP_TEST_TMP") or (Path(__file__).resolve().parent.parent / ".codex-tmp"))
    temporary = temporary.resolve() / "worker-temp"
    temporary.mkdir(parents=True, exist_ok=True)
    for name in ("TMP", "TEMP", "TMPDIR"):
        env[name] = str(temporary)
    return env


def worker_call(arguments, timeout):
    command = [sys.executable, "-B", "-m", "agent.verify_worker", *arguments]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env=child_environment(), cwd=Path(__file__).resolve().parent.parent,
                               start_new_session=os.name != "nt")
    try:
        stdout, stderr = process.communicate(timeout=max(0.1, timeout))
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        stop_worker(process)
        if isinstance(error, KeyboardInterrupt):
            raise
        return {"ok": False, "infrastructure_error": "Browser verification exceeded its time budget",
                "smoke": {"passed": False}, "tests": [], "runtime_errors": []}
    try:
        result = json.loads(stdout.decode("utf-8"))
        if not isinstance(result, dict):
            raise ValueError("Worker returned a non-object")
        return result
    except (ValueError, UnicodeError):
        return {"ok": False, "infrastructure_error": "Verification worker failed: " +
                stderr.decode("utf-8", errors="replace")[-2000:],
                "smoke": {"passed": False}, "tests": [], "runtime_errors": []}


def stop_worker(process):
    """Best-effort targeted tree cleanup, including timeout and Ctrl+C paths."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except (OSError, subprocess.TimeoutExpired):
        pass
    if process.poll() is None:
        process.kill()
    try:
        process.communicate(timeout=3)
    except subprocess.TimeoutExpired:
        # Do not hang forever on inherited browser pipe handles.
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream:
                stream.close()


def preflight(timeout=25):
    return worker_call(["--preflight"], timeout)


def verify(game: Path, plan: Path, evidence: Path, timeout=60, headful=False):
    args = ["--game", str(game.resolve()), "--plan", str(plan.resolve()),
            "--evidence", str(evidence.resolve())]
    if headful:
        args.append("--headful")
    return worker_call(args, timeout)
