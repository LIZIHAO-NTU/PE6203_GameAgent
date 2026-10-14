"""Pre-freeze review of plans, never post-hoc adjustment to generated game behavior."""
from collections import Counter
import hashlib
import json

from .contracts import compare, require, test_steps, validate_plan


EXECUTION_CONTRACT = {
    "isolation": "Each test runs on its own NEW page at the original initial state.",
    "setup": "Optional setup_steps use ordinary input/observation before this test's check steps.",
    "no_inheritance": "No state or captures carry between tests; repeat all prerequisites locally.",
    "limits": {"combined_setup_and_check_steps": 18, "plan_wait_budget_ms": 45000,
               "individual_wait_or_hold_ms": 2000, "individual_goal_timeout_ms": 8000},
    "safety": "No state setters, injected game scripts or weakening frozen acceptance.",
}


class PlanReviewError(ValueError):
    """A requested pre-freeze review could not establish a usable plan."""


def initial_assertions(test):
    """Only consecutive literal equality observations before any action/time advance."""
    records = []
    for index, step in enumerate(test_steps(test), 1):
        if step["action"] not in {"assert", "assert_consistent"}:
            break
        if step["action"] != "assert" or step.get("op") != "eq" or "value" not in step:
            continue
        if step["source"] not in {"state", "text", "attribute", "count", "enabled", "visible"}:
            continue
        identity = (step["source"], step.get("path"), step.get("selector"), step.get("attribute"))
        records.append((identity, step["value"], index))
    return records


def inspect_plan(plan):
    """Find contradictions in a draft's own initial assertions, not infer game rules."""
    tests = plan.get("tests", [])
    ordered = sorted(tests, key=lambda t: t.get("purpose") != "initial")
    anchors, warnings = {}, []
    for test in ordered:
        for identity, value, index in initial_assertions(test):
            if identity in anchors and not compare(anchors[identity][0], "eq", value):
                warnings.append({"test_id": test["id"], "kind": "fresh_page_initial_conflict",
                    "step": index, "anchor_test_id": anchors[identity][1],
                    "observation": list(identity), "anchor_value": anchors[identity][0], "expected": value,
                    "message": "Fresh-page initial assertions disagree before any setup/input. Review missing setup or non-deterministic assumptions; not proof of a game bug."})
            else:
                anchors.setdefault(identity, (value, test["id"]))
    return {"warnings": warnings, "execution_contract": EXECUTION_CONTRACT,
            "note": "Heuristic review only. It cannot solve arbitrary maps, prove rules, or guarantee semantic correctness."}


def validate_audit(value, draft):
    """Allow evidence-explained plan edits ONLY before any game exists or tests freeze."""
    require(isinstance(value, dict), "Audit must be an object")
    status = value.get("status")
    require(isinstance(status, str) and status in {"approved", "revised", "unverified"}, "Invalid audit status")
    require(not set(value) - {"status", "reason", "issues", "plan"}, "Audit contains unexpected fields")
    require(isinstance(value.get("reason"), str) and 0 < len(value["reason"]) <= 1500, "Audit needs a short reason")
    issues = value.get("issues")
    require(isinstance(issues, list) and len(issues) <= 10, "Audit needs bounded issues")
    old_tests = {t["id"]: t for t in draft["tests"]}
    for issue in issues:
        require(isinstance(issue, dict) and set(issue) == {"test_id", "reason", "spec_evidence"}, "Invalid audit issue")
        require(isinstance(issue["test_id"], str) and (issue["test_id"] in old_tests or issue["test_id"] == "plan"), "Audit cites an unknown test")
        for key in ("reason", "spec_evidence"):
            require(isinstance(issue[key], str) and 0 < len(issue[key]) <= 2000, "Audit needs original-spec evidence")
    if status != "revised":
        require("plan" not in value, "Only a revised audit may include a plan")
        require(status != "approved" or not issues, "Approved audit cannot contain unresolved issues")
        return draft, value
    require(bool(issues), "Revised audit needs cited issues")
    revised = validate_plan(value.get("plan"))
    require(revised["supported"], "Audit cannot substitute unsupported for the original plan")
    old_requirements = {r["id"]: r for r in draft["requirements"]}
    new_requirements = {r["id"]: r for r in revised["requirements"]}
    require(set(old_requirements) == set(new_requirements), "Audit cannot add/remove requirement commitments")
    for rid, old in old_requirements.items():
        new = new_requirements[rid]
        require(all(old.get(k, "core" if k == "priority" else None) == new.get(k, "core" if k == "priority" else None)
                    for k in ("text", "verification", "priority")), "Audit changed a requirement commitment: " + rid)
    require(revised["state_contract"] == draft["state_contract"], "Audit cannot change the observation contract")
    require(revised.get("manual_checks", []) == draft.get("manual_checks", []), "Audit cannot discard manual checks")
    new_tests = {t["id"]: t for t in revised["tests"]}
    require(set(new_tests) == set(old_tests), "Audit must retain every test ID")
    cited = {i["test_id"] for i in issues}
    for tid, old in old_tests.items():
        if old != new_tests[tid]:
            require(tid in cited, "Each edited test needs a specific issue: " + tid)
            require(old["requirement_ids"] == new_tests[tid]["requirement_ids"], "Audit cannot move test coverage")
        def assertion_shapes(test):
            return Counter(json.dumps({k: v for k, v in step.items() if k not in {"value", "value_from"}}, sort_keys=True)
                           for step in test_steps(test) if step["action"] in {"assert", "assert_consistent"})
        require(not (assertion_shapes(old) - assertion_shapes(new_tests[tid])),
                "Audit cannot remove assertions or weaken/change observation operators: " + tid)
    require(any(old_tests[tid] != new_tests[tid] for tid in old_tests), "Revised audit did not change a test")
    return revised, value


def failure_fingerprint(result):
    """Identify repeated identical assertion evidence; never diagnose root cause."""
    if result.get("runtime_errors") or result.get("infrastructure_error") or result.get("artifact_errors"):
        return None
    records = []
    for test in result.get("tests", []):
        if test.get("passed") is True:
            continue
        observations = test.get("observations", [])
        if test.get("failure_kind") != "assertion_mismatch" or not observations:
            return None
        last = observations[-1]
        if not all(k in last for k in ("actual", "expected", "op")):
            return None
        records.append({"id": test["id"], "step": test.get("failed_step"),
                        **{k: last[k] for k in ("actual", "expected", "op")}})
    return hashlib.sha256(json.dumps(sorted(records, key=lambda x: x["id"]), sort_keys=True).encode()).hexdigest() if records else None
