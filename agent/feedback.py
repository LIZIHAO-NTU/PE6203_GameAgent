"""Bounded, evidence-linked feedback; no rule inference, test edits or extra model calls."""
from .contracts import PlanValidationError, test_steps, validate_plan
from .state import compact_failure


def validation_feedback(error, draft=None):
    """Read-only diagnostics: first error per isolated test, never an acceptance path."""
    primary = {"location": getattr(error, "location", "$"),
               "detail": getattr(error, "detail", str(error))[:1500]}
    issues, seen = [primary], {(primary["location"], primary["detail"])}
    tests = draft.get("tests", []) if isinstance(draft, dict) else []
    scanned = 0
    for index, test in enumerate(tests[:10] if isinstance(tests, list) else []):
        if len(issues) >= 8:
            break
        scanned += 1
        # Keep the complete requirement/contract metadata. Ignore global coverage
        # failures caused by isolation; only a test-local error is useful here.
        probe = {**draft, "tests": [test]}
        try:
            validate_plan(probe)
        except PlanValidationError as found:
            if not found.location.startswith("tests[0]"):
                continue
            issue = {"location": found.location.replace("tests[0]", f"tests[{index}]", 1),
                     "detail": found.detail[:1500]}
            key = (issue["location"], issue["detail"])
            if key not in seen:
                issues.append(issue)
                seen.add(key)
    return {**primary, "issues": issues, "tests_scanned": scanned,
            "tests_not_scanned": max(0, len(tests) - scanned) if isinstance(tests, list) else 0,
            "scope": "Bounded first-known error per test plus the original failure; not exhaustive and never proof that other fields are valid.",
            "policy": "Correct all listed draft issues against the execution contract. Preserve original requirements and asserted rules; do not infer new expected values from implementation. Only full validate_plan can accept a plan."}


def repair_feedback(result, plan):
    packet = compact_failure(result)
    tests = {test["id"]: test for test in plan.get("tests", [])}
    requirements = {item["id"]: item["text"] for item in plan.get("requirements", [])}
    scenarios = []
    failed = [test for test in result.get("tests", []) if test.get("passed") is not True]
    for failure in failed[:3]:
        original = tests.get(failure.get("id"))
        if original is None:
            continue
        steps = test_steps(original)
        index = failure.get("failed_step")
        valid_index = type(index) is int and 1 <= index <= len(steps)
        rules = [{"id": rid, "text": requirements[rid][:1000]}
                 for rid in original["requirement_ids"][:4] if rid in requirements]
        scenarios.append({"test_id": original["id"], "description": original["description"][:500],
            "requirements": rules, "failed_step": index,
            "frozen_action": steps[index - 1] if valid_index else None,
            "setup_count": len(original.get("setup_steps", [])),
            "reproduce": steps[:index] if valid_index else steps,
            "test_basis_claim": original.get("evidence"),
            "note": "Requirements and basis are model-authored claims. Check original_spec; frozen expectations may be wrong. Never adjust rules to satisfy a contradictory test."})
    # Never cut a JSON object mid-string: omit an overlarge context packet, not acceptance.
    import json
    while scenarios and len(json.dumps(scenarios, ensure_ascii=False)) > 16000:
        scenarios.pop()
    packet.update(scenarios=scenarios,
        scenario_count_omitted=len(failed) - len(scenarios),
        passed_test_ids=[t["id"] for t in result.get("tests", []) if t.get("passed") is True],
        policy="Repair demonstrated implementation errors locally. If original_spec conflicts with a frozen expectation, return blocked with evidence; do not edit tests, invent state, or change mandatory game rules. Full raw evidence remains in traces.")
    return packet
