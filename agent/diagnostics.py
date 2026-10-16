"""Evidence-based routing. A test failure is not a proven root cause."""


def route_failure(result, plan_review=None, repeated_failure=False):
    kinds = sorted({t.get("failure_kind", "unclassified") for t in result.get("tests", [])
                    if t.get("passed") is not True})
    action = "repair_code"
    instruction = "Repair only the observed implementation defect; preserve all original requirements and fixed tests."
    if result.get("ok"):
        action, instruction = "complete", "Selected checks passed; full acceptance is still separate."
    elif result.get("infrastructure_error"):
        action, instruction = "stop_infrastructure", "Host/browser failure is not fixed by rewriting gameplay."
    elif result.get("artifact_errors") or result.get("runtime_errors"):
        instruction = "Fix missing local resources or the recorded runtime error before changing game rules."
    elif not result.get("quality_gate", {}).get("functional_evidence_present", True):
        action, instruction = "stop_unverified", "A functional plan is missing; do not edit game rules to manufacture evidence."
    elif result.get("quality_gate", {}).get("evidence_complete") is False:
        action, instruction = "stop_unverified", "The verifier did not return complete evidence; do not treat this as a gameplay diagnosis."
    elif any(w["test_id"] in {t["id"] for t in result.get("tests", []) if t.get("passed") is not True}
             for w in (plan_review or {}).get("warnings", []) if w.get("blocking_failure_review", True)):
        action, instruction = "stop_test_review", "A failed test has a fresh-page or temporal-capture review warning. Preserve the game and frozen tests; review the plan rather than blindly rewriting gameplay. This is not proof the game is correct."
    elif repeated_failure:
        action, instruction = "stop_test_review", "Identical assertion evidence repeated after repair. Preserve the best artifact; root cause remains unverified, not automatically a test bug."
    elif set(kinds).intersection({"assertion_mismatch", "goal_timeout", "interaction_error"}):
        action = "review_failure"
        instruction = ("Check original rules, actual/expected observations and legal reachability first. "
                       "Do not alter tests, fake state, move targets or change speeds merely to satisfy a test. "
                       "If implementation is wrong, repair locally; if uncertain, say so.")
    elif set(kinds).intersection({"state_contract_error", "state_dom_mismatch"}):
        instruction = "Align the read-only snapshot and DOM with real live state; do not fake either observation."
    return {"action": action, "failure_kinds": kinds, "instruction": instruction}


def validate_diagnosis(value, result):
    if not isinstance(value, dict) or not isinstance(value.get("category"), str) or value["category"] not in {"code_error", "test_issue", "tool_limit", "uncertain"}:
        raise ValueError("Invalid diagnosis category")
    reason = value.get("reason")
    ids = value.get("evidence_test_ids")
    failed = {t["id"] for t in result.get("tests", []) if t.get("passed") is not True}
    if not isinstance(reason, str) or not 1 <= len(reason) <= 1500:
        raise ValueError("Diagnosis needs a short evidence-based reason")
    if not isinstance(ids, list) or not ids or any(not isinstance(i, str) or i not in failed for i in ids):
        raise ValueError("Diagnosis must cite actual failed test IDs")
    if set(value) - {"category", "reason", "evidence_test_ids"}:
        raise ValueError("Diagnosis may not contain edits or revised tests")
    return value


def validate_blocked_repair(response, result, has_base):
    """Shared live/probe protocol: no edits and only actual failed-test evidence."""
    if (not isinstance(response, dict) or "blocked" not in response
            or set(response) - {"blocked", "summary"} or not has_base
            or not isinstance(result, dict) or "tests" not in result):
        raise ValueError("Blocked response requires prior failed verification and no proposed file edits")
    if "summary" in response and (not isinstance(response["summary"], str) or len(response["summary"]) > 1500):
        raise ValueError("Optional blocked summary must be a string of at most 1500 characters")
    blocked = validate_diagnosis(response["blocked"], result)
    if blocked["category"] == "code_error":
        raise ValueError("A demonstrated code error should be repaired, not labelled blocked")
    return blocked
