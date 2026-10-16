"""Validate the frozen test plan and generated paths before any file is written."""
import json
import math
from copy import deepcopy
from contextvars import ContextVar
from pathlib import Path, PurePosixPath
import re

ALLOWED_SUFFIXES = {".html", ".css", ".js", ".json", ".svg", ".txt", ".md"}
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)),
            *(f"LPT{i}" for i in range(10))}
OPS = {"eq", "ne", "gt", "ge", "lt", "le", "contains"}
_plan_location = ContextVar("plan_validation_location", default=None)


class PlanValidationError(ValueError):
    """Machine-readable location without changing a rejected plan."""
    def __init__(self, message, location):
        self.location = location
        self.detail = message
        super().__init__(f"{location}: {message}")


def require(condition, message):
    if not condition:
        if _plan_location.get() is not None:
            raise PlanValidationError(message, _plan_location.get())
        raise ValueError(message)


def bounded_text(value, label, limit=2000):
    require(isinstance(value, str) and 0 < len(value) <= limit, f"Invalid {label}")
    return value


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,39}", value),
            "IDs/capture names must be short ASCII identifiers")
    return value


def state_path(value):
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*", value)
            and len(value) <= 200 and not any(p.startswith("__") for p in value.split(".")),
            "Invalid state path")


def milliseconds(value):
    require(type(value) is int and 0 <= value <= 2000, "Wait/hold must be 0..2000 ms")
    return value


def validate_condition(step, captures):
    require(step.get("op") in OPS, "Invalid comparison operator")
    source = step.get("source")
    require(source in {"state", "text", "value", "visible", "surface", "count", "attribute", "enabled"},
            "Invalid observation source")
    if source == "state":
        state_path(step.get("path"))
    else:
        bounded_text(step.get("selector"), "selector", 500)
    if source == "surface":
        require(step.get("property") in {"width", "height", "css_width", "css_height"},
                "Invalid surface property")
    if source == "attribute":
        require(isinstance(step.get("attribute"), str) and
                re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,59}", step["attribute"]), "Invalid attribute")
    require(("value" in step) != ("value_from" in step), "Condition needs exactly one expected value")
    if "value_from" in step:
        ref = step["value_from"]
        require(isinstance(ref, dict) and ref.get("capture") in captures, "Unknown earlier capture")
        state_path(ref.get("path"))
    else:
        require(len(json.dumps(step["value"], allow_nan=False)) <= 4000, "Expected value too large")


def goal_budget(step):
    timeout = step.get("timeout_ms", 5000)
    require(type(timeout) is int and 100 <= timeout <= 8000, "Goal timeout must be 100..8000 ms")
    poll = step.get("poll_ms", 50)
    require(type(poll) is int and 20 <= poll <= 250, "Goal poll must be 20..250 ms")
    return timeout


def pointer_position(value):
    require(isinstance(value, dict) and set(value) == {"x", "y"}, "Position needs x/y")
    require(all(type(v) in {int, float} and math.isfinite(v) and 0 <= v <= 4096
                for v in value.values()), "Position must be finite, nonnegative and <=4096")


def validate_pointer(step):
    bounded_text(step.get("selector"), "pointer selector", 500)
    if "position" in step:
        pointer_position(step["position"])
    require(step.get("coordinate_space", "css") in {"css", "canvas"}, "Invalid coordinate space")
    require(step.get("button", "left") in {"left", "right", "middle"}, "Invalid mouse button")


def plan_warnings(plan):
    """Advisory only: never silently change a frozen test or mark it passed."""
    warnings = []
    for test in plan.get("tests", []):
        steps = test_steps(test)
        fixed_movement = any(s["action"] == "key" and s.get("hold_ms", 0) for s in steps)
        goal_action = any(s["action"] in {"move_to", "key_until", "wait_until"} for s in steps)
        rule_assert = any(s["action"] == "assert" and s.get("source") == "state" and
                          re.search(r"score|won|win|collect|victory", s.get("path", ""), re.I)
                          for s in steps)
        if fixed_movement and rule_assert and not goal_action:
            warnings.append({"test_id": test["id"], "kind": "fixed_timing_rule_check",
                             "message": "Fixed key duration precedes a score/win check; review whether the target is actually reached."})
    return warnings


def test_steps(test):
    """Setup is ordinary user input on this test's own fresh page, never a state setter."""
    return test.get("setup_steps", []) + test["steps"]


def validate_expected_observations(test):
    """Compare model-declared outcome summaries with assertions, never infer game truth."""
    evidence = test.get("evidence", {})
    if "expected_observations" not in evidence:
        return
    records = evidence["expected_observations"]
    require(isinstance(records, list) and len(records) <= 18, "Need 0..18 expected observations")
    steps = test_steps(test)
    targets = {i: step for i, step in enumerate(steps, 1) if step["action"] == "assert" and "value" in step}
    if all(isinstance(record, dict) and set(record) == {"value"} for record in records):
        require(len(records) == len(targets), "Expected observations must cover every literal assertion in this test")
        records = [{"step": index, "value": record["value"]}
                   for index, record in zip(targets, records)]
    seen = set()
    for record in records:
        require(isinstance(record, dict) and set(record) == {"step", "value"}, "Expected observation needs step/value only")
        index = record["step"]
        require(type(index) is int and index in targets and index not in seen, "Expected observation targets an unknown/duplicate literal assertion")
        require(len(json.dumps(record["value"], allow_nan=False)) <= 4000, "Expected observation too large")
        require(compare(record["value"], "eq", targets[index]["value"]),
                f"Test {test['id']} step {index}: outcome summary disagrees with assertion; reconcile from original spec BEFORE freezing")
        seen.add(index)
    require(seen == set(targets), "Expected observations must cover every literal assertion in this test")


def validate_plan(plan: dict) -> dict:
    token = _plan_location.set("$")
    try:
        return _validate_plan(plan)
    except PlanValidationError:
        raise
    except (ValueError, TypeError, KeyError) as error:
        raise PlanValidationError(str(error), _plan_location.get()) from error
    finally:
        _plan_location.reset(token)


def _validate_plan(plan: dict) -> dict:
    require(isinstance(plan, dict) and type(plan.get("supported")) is bool, "Missing supported boolean")
    plan = deepcopy(plan)  # Canonicalization must not rewrite the original model response.
    if not plan["supported"]:
        bounded_text(plan.get("reason"), "unsupported reason")
        return plan
    bounded_text(plan.get("title"), "title", 200)
    if "gameplay" in plan:
        gameplay = plan["gameplay"]
        require(isinstance(gameplay, dict), "Invalid gameplay analysis")
        require(gameplay.get("interaction_model") in {"real_time", "turn_based", "hybrid"},
                "Invalid interaction model")
        require(gameplay.get("input_mode") in {"keyboard", "pointer", "mixed"}, "Invalid input mode")
        bounded_text(gameplay.get("core_loop"), "core gameplay loop")
        invariants = gameplay.get("invariants")
        require(isinstance(invariants, list) and 0 < len(invariants) <= 8, "Need 1..8 rule invariants")
        for invariant in invariants:
            bounded_text(invariant, "rule invariant")
    contract = plan.get("state_contract")
    require(isinstance(contract, dict) and 0 < len(contract) <= 40, "Missing state_contract")
    flattened = {}
    def flatten(node, prefix="", depth=0):
        require(depth <= 8, "State contract nesting too deep")
        for key, value in node.items():
            state_path(key)
            path = f"{prefix}.{key}" if prefix else key
            state_path(path)
            if isinstance(value, dict):
                require(bool(value), "Empty state contract object")
                flatten(value, path, depth + 1)
            else:
                require(path not in flattened, "Duplicate flattened state path")
                bounded_text(value, "state description", 500)
                flattened[path] = value
    flatten(contract)
    require(len(flattened) <= 40, "Too many state contract fields")
    plan["state_contract"] = contract = flattened
    for path, description in contract.items():
        state_path(path)
        bounded_text(description, "state description", 500)
    development = plan.get("development_plan")
    require(isinstance(development, list) and 0 < len(development) <= 12, "Invalid development_plan")
    for task in development:
        bounded_text(task, "development task")
    requirements = plan.get("requirements")
    require(isinstance(requirements, list) and 0 < len(requirements) <= 12, "Need 1..12 requirements")
    ids, automated, manual = set(), set(), set()
    for requirement_index, item in enumerate(requirements):
        _plan_location.set(f"requirements[{requirement_index}]")
        require(isinstance(item, dict), "Invalid requirement record")
        rid = identifier(item.get("id"))
        require(rid not in ids, "Duplicate requirement id")
        ids.add(rid)
        bounded_text(item.get("text"), "requirement")
        require(item.get("priority", "core") in {"core", "secondary", "visual"}, "Invalid priority")
        require(item.get("verification") in {"automated", "manual"}, "Invalid verification mode")
        (automated if item["verification"] == "automated" else manual).add(rid)
    _plan_location.set("tests")
    tests = plan.get("tests")
    require(isinstance(tests, list) and 0 < len(tests) <= 10, "Need 1..10 automated tests")
    seen, covered, total_wait = set(), set(), 0
    for test_index, test in enumerate(tests):
        test_location = f"tests[{test_index}]"
        _plan_location.set(test_location)
        require(isinstance(test, dict), "Invalid test record")
        tid = identifier(test.get("id"))
        test_location += f" ({tid})"
        _plan_location.set(test_location)
        require(tid not in seen, "Duplicate test id")
        seen.add(tid)
        bounded_text(test.get("description"), "test description")
        if "evidence" in test:
            evidence = test["evidence"]
            require(isinstance(evidence, dict) and {"spec_quote", "expected_basis"} <= set(evidence)
                    and not set(evidence) - {"spec_quote", "expected_basis", "expected_observations"},
                    "Test evidence needs spec_quote/expected_basis and optional expected_observations")
            bounded_text(evidence["spec_quote"], "test specification quote", 1000)
            bounded_text(evidence["expected_basis"], "test expected-outcome basis", 1000)
        if "purpose" in test:
            from .quality import PURPOSES
            require(isinstance(test["purpose"], str) and test["purpose"] in PURPOSES, "Invalid test purpose")
        related = test.get("requirement_ids")
        require(isinstance(related, list) and related and all(isinstance(x, str) and x in automated for x in related),
                "Tests must reference automated requirements only")
        covered.update(related)
        body = test.get("steps")
        setup = test.get("setup_steps", [])
        require(isinstance(body, list) and 0 < len(body) <= 18, "Need 1..18 steps/test")
        require(isinstance(setup, list) and len(setup) <= 17, "Invalid setup_steps")
        steps = test_steps(test)
        require(len(steps) <= 18, "Setup and check together need 1..18 steps/test")
        captures, assertions = set(), 0
        for step_index, step in enumerate(steps):
            setup_count = len(setup)
            stage = "setup_steps" if step_index < setup_count else "steps"
            local_index = step_index if stage == "setup_steps" else step_index - setup_count
            _plan_location.set(f"{test_location}.{stage}[{local_index}] (combined step {step_index + 1})")
            require(isinstance(step, dict), "Invalid step")
            action = step.get("action")
            if action in {"click", "hover", "drag"}:
                validate_pointer(step)
                if action == "drag":
                    require("position" in step, "Drag needs start position")
                    pointer_position(step.get("to"))
                    require(type(step.get("steps", 8)) is int and 1 <= step.get("steps", 8) <= 20,
                            "Drag needs 1..20 interpolation steps")
            elif action in {"fill", "select_option"}:
                bounded_text(step.get("selector"), "selector", 500)
                if action == "fill":
                    require(isinstance(step.get("text"), str) and len(step["text"]) <= 500,
                            "Fill needs text of 0..500 characters")
                else:
                    bounded_text(step.get("value"), "option value", 200)
            elif action == "key":
                bounded_text(step.get("key"), "key", 80)
                total_wait += milliseconds(step.get("hold_ms", 0))
            elif action == "keys":
                keys = step.get("keys")
                require(isinstance(keys, list) and 1 <= len(keys) <= 4, "Need 1..4 simultaneous keys")
                for key in keys:
                    bounded_text(key, "key", 80)
                require(len(set(keys)) == len(keys), "Duplicate simultaneous key")
                total_wait += milliseconds(step.get("hold_ms", 100))
            elif action == "wait":
                total_wait += milliseconds(step.get("ms"))
            elif action == "capture":
                captures.add(identifier(step.get("name")))
            elif action == "sample":
                name = identifier(step.get("name"))
                require(len(name) <= 30, "Sample name too long")
                count = step.get("samples", 3)
                require(type(count) is int and 2 <= count <= 8, "Need 2..8 temporal samples")
                duration = milliseconds(step.get("duration_ms", 500))
                require(duration >= count - 1, "Temporal samples need a positive interval")
                total_wait += duration
                captures.update({name + "_start", name + "_end"})
            elif action in {"wait_until", "key_until", "move_to"}:
                total_wait += goal_budget(step)
                condition = step.get("until")
                require(isinstance(condition, dict), "Goal action needs an until condition")
                validate_condition(condition, captures)
                if action == "key_until":
                    bounded_text(step.get("key"), "key", 80)
                if action == "move_to":
                    for label in ("actor", "target"):
                        paths = step.get(label)
                        require(isinstance(paths, dict) and set(paths) == {"x", "y"}, "Need x/y state paths")
                        for path in paths.values():
                            state_path(path)
                    keys = step.get("keys")
                    require(isinstance(keys, dict) and set(keys) == {"left", "right", "up", "down"},
                            "move_to needs four direction keys")
                    for key in keys.values():
                        bounded_text(key, "direction key", 80)
                    tolerance = step.get("tolerance", 4)
                    require(type(tolerance) in {int, float} and math.isfinite(tolerance) and 0 < tolerance <= 30,
                            "Tolerance must be finite and >0..30")
            elif action == "assert_stable":
                assertions += 1
                duration = milliseconds(step.get("duration_ms", 300))
                count = step.get("samples", 3)
                require(type(count) is int and 2 <= count <= 8, "Need 2..8 stability samples")
                require(duration >= 100, "Stability observation needs 100..2000 ms")
                require(not any(k in step for k in ("value", "value_from", "op")),
                        "Stability compares actual samples, not expected-value overrides")
                validate_condition({**step, "op": "eq", "value": None}, captures)
                total_wait += duration
            elif action == "assert_consistent":
                assertions += 1
                state_path(step.get("state_path"))
                require(step.get("source") in {"text", "value", "count", "attribute", "enabled", "surface"},
                        "Consistency check needs an independent DOM observation")
                require(step.get("coerce", "none") in {"none", "number"}, "Invalid consistency conversion")
                require(not any(k in step for k in ("value", "value_from", "op")),
                        "Consistency uses live state, not an expected-value override")
                validate_condition({**step, "op": "eq", "value": None}, captures)
            elif action == "assert":
                assertions += 1
                validate_condition(step, captures)
            else:
                raise ValueError(f"Unsupported test action: {action}")
        _plan_location.set(test_location)
        require(assertions > 0, "Every test needs an assertion")
        require(any(s["action"] in {"assert", "assert_consistent", "assert_stable"} for s in body),
                "Every test needs an assertion in check steps, not only setup")
        validate_expected_observations(test)
    _plan_location.set("tests")
    require(total_wait <= 45000, "Plan waits/holds/goal budgets exceed 45 seconds")
    require(covered == automated, "Every automated requirement must have a test; missing IDs: "
            + ", ".join(sorted(automated - covered)))
    _plan_location.set("manual_checks")
    manual_checks = plan.get("manual_checks", [])
    require(isinstance(manual_checks, list) and len(manual_checks) <= 6, "Invalid manual_checks")
    manual_covered = set()
    for manual_index, check in enumerate(manual_checks):
        _plan_location.set(f"manual_checks[{manual_index}]")
        require(isinstance(check, dict) and check.get("requirement_id") in ids, "Invalid manual check")
        if check["requirement_id"] in manual:
            manual_covered.add(check["requirement_id"])
        bounded_text(check.get("instruction"), "manual instruction")
    require(manual_covered == manual, "Every manual requirement needs a manual check; missing IDs: "
            + ", ".join(sorted(manual - manual_covered)))
    return plan


def safe_relative_path(value: str) -> PurePosixPath:
    require(isinstance(value, str) and len(value) <= 180, "Invalid path")
    require("\\" not in value and ":" not in value and not value.startswith("/"), "Only relative slash paths allowed")
    path = PurePosixPath(value)
    require(path.parts and str(path) == value, "Non-canonical path")
    for part in path.parts:
        require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", part) and not part.endswith("."), "Unsafe path segment")
        require(part.split(".")[0].upper() not in RESERVED and part not in {".", ".."}, "Reserved path")
    require(path.suffix.lower() in ALLOWED_SUFFIXES, "Executable/backend/binary files not allowed in this MVP")
    return path


def validate_bundle(bundle: dict):
    files = bundle.get("files")
    require(isinstance(files, list) and 0 < len(files) <= 20, "Need 1..20 files")
    validated, seen, total = [], set(), 0
    for item in files:
        require(isinstance(item, dict), "Invalid file record")
        path = safe_relative_path(item.get("path"))
        content = item.get("content")
        require(isinstance(content, str), "File contents must be text")
        total += len(content.encode("utf-8"))
        require(total <= 400_000, "Bundle exceeds 400 KB")
        key = str(path).lower()
        require(key not in seen, "Duplicate/case-colliding file")
        seen.add(key)
        validated.append((path, content))
    require("index.html" in {str(p) for p, _ in validated}, "Missing lowercase index.html")
    for path, _ in validated:
        require(not any(str(parent).lower() in seen for parent in path.parents if str(parent) != "."),
                "A file path collides with a directory")
    return validated


def write_bundle(bundle: dict, root: Path) -> None:
    validated = validate_bundle(bundle)
    require(not root.exists(), "Candidate directory already exists; refusing to overwrite")
    root.mkdir(parents=True)
    for path, content in validated:
        target = root.joinpath(*path.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def lookup(state, path):
    """Observe nested snapshots or literal dotted keys; reject conflicting evidence."""
    flat_present = isinstance(state, dict) and path in state
    value = state
    try:
        for part in path.split("."):
            value = value[int(part)] if isinstance(value, list) and part.isdigit() else value[part]
    except (KeyError, IndexError, TypeError):
        if flat_present:
            return state[path]
        raise
    if flat_present:
        require(compare(value, "eq", state[path]), "Ambiguous snapshot: flat and nested values disagree for " + path)
    return value


def compare(actual, op, expected):
    if op in {"gt", "ge", "lt", "le"}:
        require(type(actual) in {int, float} and type(expected) in {int, float}, "Ordering requires numbers")
        require(math.isfinite(actual) and math.isfinite(expected), "Nonfinite observation")
    if op == "eq":
        return type(actual) is type(expected) and actual == expected or (
            type(actual) in {int, float} and type(expected) in {int, float} and actual == expected)
    if op == "ne":
        return not compare(actual, "eq", expected)
    if op == "gt":
        return actual > expected
    if op == "ge":
        return actual >= expected
    if op == "lt":
        return actual < expected
    if op == "le":
        return actual <= expected
    if op == "contains":
        return expected in actual
    raise ValueError("Unknown comparison")
