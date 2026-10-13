"""Opt-in observations of verified recoveries, not learned game implementations."""
import json
import hashlib
import os
from pathlib import Path
import tempfile

RULES = {
    "state_dom_mismatch": "Keep rendering, rules and read-only snapshots aligned with one live state.",
    "state_contract_error": "Return fresh serializable snapshots with the promised paths; never fabricate values.",
    "runtime_error": "Fix the recorded runtime failure before changing gameplay mechanics.",
    "goal_timeout": "Check legal reachability and input strategy; a timeout alone does not identify a code defect.",
    "interaction_error": "Verify focus, selectors and actual enabled controls before changing game rules.",
    "assertion_mismatch": "Compare the fixed expectation with original rules and actual observations; do not weaken tests."
}


def load_lessons(path):
    path = Path(path)
    if path.suffix.lower() != ".json" or path.is_symlink():
        raise ValueError("Lessons require a non-symlink JSON file")
    if not path.exists():
        return {"schema_version": 1, "records": [], "_sha256": None}
    if path.stat().st_size > 128000:
        raise ValueError("Lesson store exceeds 128KB")
    payload = path.read_bytes()
    data = json.loads(payload.decode("utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("records"), list):
        raise ValueError("Invalid lesson store")
    if len(data["records"]) > len(RULES):
        raise ValueError("Too many lesson rules")
    seen = set()
    for row in data["records"]:
        if not isinstance(row, dict) or row.get("rule_id") not in RULES or row["rule_id"] in seen:
            raise ValueError("Unknown or duplicate lesson rule")
        if not isinstance(row.get("evidence"), list) or len(row["evidence"]) > 5:
            raise ValueError("Invalid lesson evidence")
        seen.add(row["rule_id"])
    # Do not load arbitrary prose, instructions or code from this editable file.
    return {"schema_version": 1, "records": [{"rule_id": r["rule_id"], "evidence": r["evidence"]} for r in data["records"]],
            "_sha256": hashlib.sha256(payload).hexdigest()}


def select_hints(store, feedback):
    kinds = {t.get("failure_kind") for t in (feedback or {}).get("tests", []) if not t.get("passed")}
    return [{"rule_id": r["rule_id"], "principle": RULES[r["rule_id"]],
             "recorded_recoveries": len(r["evidence"])}
            for r in store.get("records", []) if r["rule_id"] in kinds and r["evidence"]][:3]


def record_recovery(path, store, memory, final, digest, plan_hash, run_id):
    if not final.get("ok") or not final.get("quality_gate", {}).get("passed"):
        return 0
    passed = {t["id"] for t in final.get("tests", []) if t.get("passed") is True}
    records = {r["rule_id"]: {"rule_id": r["rule_id"], "evidence": list(r["evidence"])} for r in store["records"]}
    added = 0
    for attempt in memory:
        if attempt.get("plan_sha256") != plan_hash or attempt["code_sha256"] == digest:
            continue
        for failure in attempt.get("feedback", {}).get("failed_tests", []):
            kind = failure.get("kind")
            if kind not in RULES or failure["id"] not in passed:
                continue
            entry = {"run_id": run_id[:100], "test_id": failure["id"], "plan_sha256": plan_hash,
                     "before_sha256": attempt["code_sha256"], "after_sha256": digest,
                     "claim": "This check failed, then passed after a code change under the same plan; root cause not proven."}
            row = records.setdefault(kind, {"rule_id": kind, "evidence": []})
            if entry not in row["evidence"]:
                row["evidence"] = (row["evidence"] + [entry])[-5:]
                added += 1
    if added:
        target = Path(path)
        if target.is_symlink() or (target.exists() and target.stat().st_size > 128000):
            raise ValueError("Lesson target changed or is unsafe")
        actual = hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
        if actual != store.get("_sha256"):
            raise ValueError("Lesson store changed concurrently; preserving the other writer's data")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(__file__).resolve().parent.parent / ".codex-tmp"
        temporary.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"schema_version": 1, "records": list(records.values())}, ensure_ascii=False, indent=2)
        if len(payload.encode("utf-8")) > 128000:
            raise ValueError("Updated lesson store too large")
        with tempfile.TemporaryDirectory(dir=temporary) as directory:
            stage = Path(directory) / "lessons.json"
            stage.write_text(payload, encoding="utf-8")
            os.replace(stage, target)
    return added
