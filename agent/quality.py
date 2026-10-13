"""Deterministic evidence gates. Structural coverage is not semantic correctness."""
from collections import Counter


INPUT_ACTIONS = {"click", "key", "keys", "drag", "key_until", "move_to"}
PURPOSES = {"initial", "legal_action", "invalid_action", "reset", "terminal", "consistency"}


def review_plan(plan):
    """Inspect an already validated plan without editing it or inventing coverage."""
    warnings, functional, purposes = [], [], set()
    core = {r["id"] for r in plan.get("requirements", [])
            if r.get("priority", "core") == "core" and r["verification"] == "automated"}
    for test in plan.get("tests", []):
        steps = test["steps"]
        purposes.add(test.get("purpose"))
        acted = False
        meaningful = False
        for step in steps:
            acted = acted or step["action"] in INPUT_ACTIONS
            if acted and step["action"] == "assert" and step["source"] in {
                    "state", "text", "attribute", "enabled", "count"}:
                meaningful = True
        if meaningful and core.intersection(test["requirement_ids"]):
            functional.append(test["id"])
        if all(s["action"] not in INPUT_ACTIONS for s in steps):
            warnings.append({"test_id": test["id"], "kind": "observation_only",
                             "message": "No input event; this test alone cannot establish interaction rules."})
    if not functional:
        warnings.append({"test_id": "plan", "kind": "no_functional_evidence",
                         "message": "No input followed by a rule observation. Startup-only evidence cannot establish functional completion."})
    for purpose in ("invalid_action", "reset", "terminal"):
        if purpose not in purposes:
            warnings.append({"test_id": "plan", "kind": "review_" + purpose,
                             "message": f"No {purpose} scenario labelled; check applicability against the original spec. Not automatically a failure."})
    if not any(s["action"] == "assert_consistent" for t in plan.get("tests", []) for s in t["steps"]):
        warnings.append({"test_id": "plan", "kind": "no_cross_observation",
                         "message": "No DOM/state consistency check. Game-supplied snapshots are not independent evidence."})
    return {"functional_test_ids": functional, "warnings": warnings,
            "note": "Labels and input/assertion structure are heuristic signals, not proof of rules or full requirement coverage."}


def completion_gate(plan, result, planning_status):
    """Recompute completion from actual evidence rather than trusting result.ok."""
    expected = {t["id"] for t in plan.get("tests", [])}
    tests = result.get("tests", [])
    counts = Counter(t.get("id") for t in tests)
    reasons = []
    if not expected or set(counts) != expected or any(n != 1 for n in counts.values()):
        reasons.append("Test evidence is empty, incomplete, duplicated or contains unknown IDs")
    if any(t.get("passed") is not True for t in tests):
        reasons.append("One or more recorded tests did not pass")
    if result.get("smoke", {}).get("passed") is not True:
        reasons.append("Rendered startup check did not pass")
    if result.get("runtime_errors") or result.get("infrastructure_error"):
        reasons.append("Runtime or verification infrastructure errors remain")
    if result.get("ok") is not True:
        reasons.append("Verifier did not report a clean run")
    review = review_plan(plan)
    functional = planning_status in {"valid", "recovered"} and bool(review["functional_test_ids"])
    if not functional:
        reasons.append("Functional acceptance has not been established by this plan")
    return {"passed": not reasons, "functional_evidence_present": functional,
            "evidence_complete": bool(expected) and set(counts) == expected and all(n == 1 for n in counts.values()),
            "reasons": reasons, "full_game_acceptance": None}
