"""Aggregate actual run summaries; never manufacture a semantic success rate."""
from collections import Counter
import csv
import json
from pathlib import Path
import statistics


def aggregate(root: Path):
    rows = []
    for path in sorted(root.glob("*/summary.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema_version") != 1:
            continue
        usage = data.get("usage", {})
        rows.append({"run_id": data["run_id"], "model": data.get("model"),
                     "agent_version": data.get("agent_version", "0.1.0-or-unknown"),
                     "prompts_sha256": data.get("prompts_sha256"),
                     "original_spec_sha256": data.get("original_spec_sha256"),
                     "automated_requirement_pass_rate": data.get("automated_requirement_pass_rate"),
                     "status": data["status"], "automated_checks_passed": bool(data.get("automated_checks_passed")),
                     "smoke_passed": bool(data.get("smoke_passed")),
                     "had_verification_failure": bool(data.get("had_verification_failure")),
                     "recovered_after_verification_failure": bool(data.get("recovered_after_verification_failure")),
                     "duration_seconds": data.get("duration_seconds", 0),
                     "first_playable_seconds": data.get("first_playable_seconds"), **usage})
    count = len(rows)
    recovery_eligible = sum(r["had_verification_failure"] for r in rows)
    totals = {"runs": count, "status_counts": dict(Counter(r["status"] for r in rows)),
              "automated_check_success_rate_over_all_runs":
                  sum(r["automated_checks_passed"] for r in rows) / count if count else None,
              "smoke_success_rate_over_all_runs": sum(r["smoke_passed"] for r in rows) / count if count else None,
              "recovery_eligible_runs": recovery_eligible,
              "recovery_success_rate": sum(r["recovered_after_verification_failure"] for r in rows) / recovery_eligible
                  if recovery_eligible else None,
              "mean_duration_seconds": statistics.mean(r["duration_seconds"] for r in rows) if count else None,
              "total_known_prompt_tokens": sum(r.get("prompt_tokens", 0) for r in rows),
              "total_known_completion_tokens": sum(r.get("completion_tokens", 0) for r in rows),
              "total_calls_with_unknown_usage": sum(r.get("calls_with_unknown_usage", 0) for r in rows),
              "full_game_acceptance_rate": None,
              "notes": ["Rates include ALL saved runs, including unsupported/error runs; no cherry-picking.",
                  "Automated checks use model-authored plans, not independent full-game acceptance.",
                  "Do not compare mixed models/prompts/specs as a controlled experiment.",
                  "Preflight failures before output creation are not model runs and are not included."]}
    return {"metrics": totals, "runs": rows}


def export(root: Path, output: Path):
    if output.suffix.lower() != ".json":
        raise ValueError("Summary output must use .json suffix")
    csv_path = output.with_suffix(".csv")
    if output.exists() or csv_path.exists():
        raise ValueError("Report exists; choose a new output name")
    report = aggregate(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = ["run_id", "model", "agent_version", "prompts_sha256", "original_spec_sha256",
              "automated_requirement_pass_rate", "status", "automated_checks_passed", "smoke_passed", "duration_seconds",
              "first_playable_seconds", "api_attempts", "prompt_tokens", "completion_tokens", "cached_input_tokens",
              "calls_with_unknown_usage", "estimated_known_usage_cost", "currency", "cost_is_complete",
              "had_verification_failure", "recovered_after_verification_failure", "note"]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(report["runs"])
    return report
