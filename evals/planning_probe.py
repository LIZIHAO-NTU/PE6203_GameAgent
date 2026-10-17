"""One-call development probe for planner quality; never generates a game."""
import argparse
import hashlib
import json
from pathlib import Path
import time

from agent.config import Config, load_dotenv
from agent.contracts import test_steps, validate_plan
from agent.plan_review import EXECUTION_CONTRACT, inspect_plan
from agent.prompts import planner_system
from agent.provider import ChatClient
from agent.trace import Trace


def assess(plan, spec):
    """Report structure and heuristic warnings, not semantic correctness."""
    valid = validate_plan(plan)
    return {
        "structurally_valid": True,
        "test_count": len(valid.get("tests", [])),
        "combined_steps_by_test": {test["id"]: len(test_steps(test)) for test in valid.get("tests", [])},
        "review_warnings": inspect_plan(valid, spec)["warnings"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("Output already exists; use a new directory")
    spec = args.spec.read_text(encoding="utf-8-sig")
    if not spec.strip() or len(spec.encode("utf-8")) > 30000:
        parser.error("Specification must be nonempty and <=30 KB")
    load_dotenv(Path.cwd() / ".env")
    config = Config.from_env()
    if not config.api_key:
        parser.error("API key is not configured")
    if config.api_key in spec:
        parser.error("Configured API key appears in specification")
    system = planner_system(False)
    prompt = json.dumps({"original_spec": spec, "validation_feedback": None,
                         "validation_details": None, "previous_plan": None,
                         "execution_contract": EXECUTION_CONTRACT}, ensure_ascii=False)
    trace = Trace(args.output / "traces", (config.api_key,))
    client = ChatClient(config, trace, max_calls=1, deadline=time.monotonic() + 120)
    report = {"spec_sha256": hashlib.sha256(spec.encode()).hexdigest(),
              "planner_sha256": hashlib.sha256(system.encode()).hexdigest(),
              "model": config.model, "max_output_tokens": min(6000, config.max_tokens),
              "max_api_attempts": 1, "generation_calls": 0}
    try:
        plan = client.ask_json("plan", system, prompt)
        trace.save("plan.json", plan)
        try:
            report.update(assess(plan, spec))
        except (ValueError, TypeError, KeyError) as error:
            report.update(structurally_valid=False, validation_error=str(error))
    except Exception as error:
        report.update(structurally_valid=False, request_error=type(error).__name__)
    report["usage"] = client.usage_summary()
    trace.save("report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["structurally_valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
