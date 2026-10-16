"""Controller-owned planning -> generation -> verification -> bounded repair loop."""
import hashlib
from collections import Counter
import json
from pathlib import Path
import shutil
import time

from . import __version__
from .contracts import plan_warnings, validate_plan, write_bundle
from .prompts import CODER_SYSTEM, planner_system, DIAGNOSTIC_SYSTEM, PLAN_AUDIT_SYSTEM
from .provider import BudgetError, ChatClient
from .trace import Trace
from .state import AgentState, bundle_digest, compact_failure
from .planning import startup_only_plan, validate_recovery
from .feedback import validation_feedback, repair_feedback
from .quality import completion_gate, review_plan
from .verification import failure_summary, preflight, verify, verify_repeated
from .editing import resolve_edit
from .artifacts import check_artifacts
from .diagnostics import route_failure, validate_diagnosis
from .evidence import runtime_metadata
from .lessons import load_lessons, select_hints, record_recovery
from .plan_review import EXECUTION_CONTRACT, PlanReviewError, inspect_plan, validate_audit, failure_fingerprint


def verification_score(result):
    smoke = bool(result.get("smoke", {}).get("passed"))
    return (bool(result.get("ok")), smoke and not bool(result.get("runtime_errors")), smoke,
            sum(bool(t.get("passed")) for t in result.get("tests", [])),
            -len(result.get("runtime_errors", [])))


def requirement_results(plan, result):
    results = {t["id"]: t for t in result.get("tests", [])}
    counts = Counter(t["id"] for t in result.get("tests", []))
    records = []
    for requirement in plan.get("requirements", []):
        related = [t["id"] for t in plan["tests"] if requirement["id"] in t["requirement_ids"]]
        checked = bool(related) and all(counts[t] == 1 and results.get(t, {}).get("passed") is True for t in related)
        records.append({**requirement, "test_ids": related,
                        "status": "automated_pass" if checked else
                        ("manual_pending" if requirement["verification"] == "manual" else "not_passed")})
    return records


def record_plan(trace, plan, name="plan.json"):
    trace.save(name, plan)
    path = trace.root / name
    payload = path.read_bytes()
    return path, payload, hashlib.sha256(payload).hexdigest()


def apply_gate(plan, result, planning_status):
    gate = completion_gate(plan, result, planning_status)
    # Keep raw verifier evidence; a controller verdict is an additional layer.
    return {**result, "verifier_ok": result.get("ok"), "ok": gate["passed"], "quality_gate": gate}


def prefer_candidate(old, new):
    passed = lambda result: {t["id"] for t in result.get("tests", []) if t.get("passed") is True}
    stable_old = (old.get("smoke", {}).get("passed") and not old.get("runtime_errors")
                  and not old.get("infrastructure_error") and old.get("quality_gate", {}).get("evidence_complete", True))
    regressions = sorted(passed(old) - passed(new)) if stable_old else []
    return not regressions and verification_score(new) >= verification_score(old), regressions


def run(config, spec_path, output, max_rounds=3, max_calls=8, max_seconds=600,
        test_timeout=60, headful=False, client_factory=ChatClient, verifier=verify,
        preflight_fn=preflight, strict_plan=False, repair_mode="auto", syntax_check=False,
        diagnose_failures=False, verify_repeats=1, lessons_path=None, plan_audit=False,
        structured_expectations=False):
    if type(structured_expectations) is not bool:
        raise ValueError("structured_expectations must be boolean")
    planning_system = planner_system(structured_expectations)
    if repair_mode not in {"auto", "full"}:
        raise ValueError("repair_mode must be auto or full")
    if type(verify_repeats) is not int or not 1 <= verify_repeats <= 3:
        raise ValueError("verify_repeats must be 1..3")
    started = time.monotonic()
    deadline = started + max_seconds
    if spec_path.suffix.lower() != ".md":
        raise ValueError("Specification input must be a Markdown .md file")
    spec = spec_path.read_text(encoding="utf-8-sig")
    if not spec.strip() or len(spec.encode("utf-8")) > 30000:
        raise ValueError("Specification must be nonempty and <=30 KB")
    if not config.api_key:
        raise ValueError("No API key: configure DEEPSEEK_API_KEY in .env or your environment")
    if config.api_key in spec:
        raise ValueError("Configured API key appears in the specification; remove it before sending")
    if output.exists():
        raise ValueError("Output already exists; choose a new path (no runs are overwritten)")
    print("[1/4] Checking local browser; no API credits used yet...", flush=True)
    check = preflight_fn(timeout=min(25, max_seconds))
    if not check.get("ok"):
        raise RuntimeError("Browser unavailable. Install requirements and Chromium, then run doctor.\n"
                           + str(check.get("infrastructure_error", "Unknown browser error")))
    output.mkdir(parents=True, exist_ok=False)
    trace = Trace(output / "traces", (config.api_key,))
    trace.save("original_spec.json", {"filename": spec_path.name, "content": spec})
    client = client_factory(config, trace, max_calls, deadline)
    summary = {"schema_version": 1, "agent_version": __version__, "run_id": output.name, "model": config.model,
               "original_spec_sha256": hashlib.sha256(spec.encode("utf-8")).hexdigest(),
               "prompts_sha256": hashlib.sha256((planning_system + CODER_SYSTEM + DIAGNOSTIC_SYSTEM + PLAN_AUDIT_SYSTEM).encode("utf-8")).hexdigest(),
               "limits": {"max_rounds": max_rounds, "max_calls": max_calls,
                          "max_seconds": max_seconds, "test_timeout": test_timeout},
               "features": {"repair_mode": repair_mode, "syntax_check": syntax_check,
                            "diagnose_failures": diagnose_failures, "verify_repeats": verify_repeats,
                            "lessons_enabled": False, "lesson_store_sha256": None, "plan_audit": plan_audit,
                            "structured_expectations": structured_expectations},
               "runtime": {**runtime_metadata(), "browser": check.get("browser_version")},
               "base_url": config.base_url, "status": "started", "automated_checks_passed": False,
               "full_game_acceptance": None, "manual_interventions_during_run": 0,
               "planning_status": "pending", "infrastructure_checks_passed": False,
               "planning_recovery_attempted": False, "planning_recovered": False,
               "plan_audit_status": "not_requested", "plan_audit_attempted": False,
               "first_playable_seconds": None, "had_verification_failure": False,
               "recovered_after_verification_failure": False, "attempts": [],
               "limitations": ["Vanilla offline 2D browser games only; not the full course scope.",
                   "Tests and implementation use the same model; shared blind spots remain.",
                   "State hooks are game-supplied observations, not independent proof.",
                   "Browser/network restrictions are defense in depth, not a hardened OS sandbox.",
                   "Automated checks passed does not mean full gameplay acceptance."]}
    plan, best, previous, feedback = None, None, None, None
    state = AgentState()
    best_bundle = None
    pending_candidate = None
    repeated_code = 0
    force_full = False
    diagnosis_attempted = False
    last_failure = None
    identical_failures = 0
    lesson_store = {"schema_version": 1, "records": []}
    lessons_enabled = False
    exit_code = 4
    try:
        trace.event("run_start", model=config.model, max_rounds=max_rounds,
                    max_calls=max_calls, max_seconds=max_seconds, browser=check)
        if lessons_path is not None:
            try:
                lesson_store = load_lessons(lessons_path)
                lessons_enabled = True
                summary["features"].update(lessons_enabled=True, lesson_store_sha256=lesson_store.get("_sha256"))
            except (OSError, ValueError, TypeError) as error:
                trace.event("lessons_disabled", reason=trace.redact(str(error)))
        print("[2/4] Planning requirements and frozen acceptance tests...", flush=True)
        plan_error = None
        plan_details = None
        raw_plan = None
        for _ in range(2):
            prompt = json.dumps({"original_spec": spec, "validation_feedback": plan_error,
                                 "validation_details": plan_details,
                                 "previous_plan": raw_plan if plan_error else None,
                                 "execution_contract": EXECUTION_CONTRACT}, ensure_ascii=False)
            raw_plan = client.ask_json("plan", planning_system, prompt)
            try:
                plan = validate_plan(raw_plan)
                break
            except (ValueError, TypeError, KeyError) as error:
                plan_error = str(error)
                plan_details = validation_feedback(error)
                trace.event("plan_validation_failed", error=plan_error, details=plan_details)
        else:
            if strict_plan or not isinstance(raw_plan, dict) or raw_plan.get("supported") is not True:
                raise ValueError("Could not produce a valid test plan: " + str(plan_error))
            # Keep the original requirements. Only our confidence/acceptance scope degrades.
            plan = validate_plan(startup_only_plan())
            summary.update(planning_status="failed_startup_only", planning_error=plan_error)
            trace.event("planning_degraded", error=plan_error,
                        decision="Generate original-spec game; startup-only checks are NOT functional acceptance")
        if summary["planning_status"] == "pending":
            summary["planning_status"] = "valid" if plan["supported"] else "unsupported"
        summary["plan_review"] = inspect_plan(plan, spec)
        if plan_audit:
            if not plan["supported"] or summary["planning_status"] != "valid":
                summary["plan_audit_status"] = "not_applicable"
            elif max_calls - client.calls < 2 or deadline - time.monotonic() < 15:
                summary["plan_audit_status"] = "skipped_budget"
                trace.event("plan_audit_skipped", reason="Reserve at least one call for generation; review not performed")
            else:
                trace.save("draft_plan.json", plan)
                summary["draft_plan_sha256"] = hashlib.sha256((trace.root / "draft_plan.json").read_bytes()).hexdigest()
                summary["plan_audit_attempted"] = True
                try:
                    raw_audit = client.ask_json("plan_audit", PLAN_AUDIT_SYSTEM, json.dumps({
                        "original_spec": spec, "draft_plan": plan,
                        "execution_contract": EXECUTION_CONTRACT, "deterministic_review": summary["plan_review"]}, ensure_ascii=False))
                    trace.save("plan_audit_response.json", raw_audit)
                    reviewed, audit = validate_audit(raw_audit, plan)
                    summary["plan_audit_status"] = audit["status"]
                    trace.save("plan_audit.json", audit)
                    if audit["status"] == "unverified":
                        raise PlanReviewError("Draft plan review is unverified: " + audit["reason"])
                    plan = reviewed
                    summary["plan_review"] = inspect_plan(plan, spec)
                except Exception as error:
                    summary["plan_audit_status"] = "unverified"
                    summary["plan_audit_error"] = trace.redact(str(error))
                    raise PlanReviewError(summary["plan_audit_error"]) from None
        summary["gameplay"] = plan.get("gameplay")
        plan_path, plan_bytes, plan_hash = record_plan(trace, plan)
        summary["plan_sha256"] = plan_hash
        summary["active_plan"] = plan_path.name
        summary["initial_plan_sha256"] = plan_hash
        summary["plan_warnings"] = plan_warnings(plan)
        summary["plan_quality"] = review_plan(plan)
        trace.save("plan_review.json", {**summary["plan_quality"], "timing_warnings": summary["plan_warnings"]})
        if not plan["supported"]:
            summary.update(status="unsupported_spec", error=plan["reason"])
            exit_code = 3
        else:
            for round_number in range(1, max_rounds + 1):
                if time.monotonic() >= deadline:
                    raise BudgetError("Run time budget reached")
                print(f"[3/4] Generation / repair {round_number}/{max_rounds}...", flush=True)
                current_feedback = repair_feedback(feedback, plan) if feedback and "tests" in feedback else feedback
                if current_feedback:
                    trace.save(f"attempts/{round_number:02d}/model_feedback.json", current_feedback)
                prompt = json.dumps({"original_spec": spec, "frozen_plan": plan,
                    "previous_version": previous, "verification_feedback": current_feedback,
                    "repair_memory": state.context(),
                    "planning_status": summary["planning_status"],
                    "requested_output_mode": "replace_files" if previous and repair_mode == "auto" and not force_full else "full",
                    "repair_base_sha256": bundle_digest(previous) if previous else None,
                    "debug_hints": select_hints(lesson_store, feedback) if lessons_enabled else [],
                    "remaining_seconds": max(0, int(deadline - time.monotonic()))}, ensure_ascii=False)
                response = client.ask_json(f"code_{round_number}", CODER_SYSTEM, prompt)
                if isinstance(response, dict) and "blocked" in response:
                    if set(response) != {"blocked"} or not best or not feedback or "tests" not in feedback:
                        raise ValueError("Blocked response requires prior failed verification and no proposed file edits")
                    blocked = validate_diagnosis(response["blocked"], feedback)
                    if blocked["category"] == "code_error":
                        raise ValueError("A demonstrated code error should be repaired, not labelled blocked")
                    summary["repair_blocked"] = blocked
                    trace.event("repair_blocked", **blocked)
                    trace.save("repair_blocked.json", blocked)
                    state.stop_reason = "diagnosis_unverified"
                    break
                attempt_dir = trace.root / "attempts" / f"{round_number:02d}"
                candidate = attempt_dir / "game"
                try:
                    bundle, edit_info = resolve_edit(response, previous, allow_partial=repair_mode == "auto" and not force_full)
                    write_bundle(bundle, candidate)
                    force_full = False
                    pending_candidate = candidate
                except (ValueError, OSError, TypeError) as error:
                    feedback = {"bundle_validation_error": str(error)}
                    force_full = True
                    summary["attempts"].append({"round": round_number, "bundle_valid": False, **feedback})
                    trace.event("bundle_rejected", round=round_number, **feedback)
                    continue
                digest = bundle_digest(bundle)
                if digest in state.tested_hashes:
                    repeated_code += 1
                    feedback = {"no_progress": "This exact source was already tested and failed.",
                                "repair_base_feedback": best[1] if best else feedback}
                    summary["attempts"].append({"round": round_number, "bundle_valid": True,
                                                "verification_skipped": "duplicate_source", "code_sha256": digest})
                    trace.event("duplicate_source", round=round_number, code_sha256=digest)
                    if repeated_code >= 2:
                        state.stop_reason = "repeated_source_without_progress"
                        break
                    continue
                if plan_path.read_bytes() != plan_bytes:
                    raise RuntimeError("Frozen plan changed unexpectedly; aborting")
                remaining = deadline - time.monotonic()
                artifacts = check_artifacts(candidate, syntax=syntax_check, timeout=min(5, max(0.1, remaining)))
                trace.save(f"attempts/{round_number:02d}/artifacts.json", artifacts)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    # Preserve valid generated source, but never call it tested.
                    result = {"ok": False, "smoke": {"passed": False}, "tests": [],
                              "infrastructure_error": "Time budget exhausted before verification"}
                elif not artifacts["ok"]:
                    result = {"ok": False, "smoke": {"passed": False}, "tests": [],
                              "runtime_errors": [], "infrastructure_error": None,
                              "artifact_errors": artifacts["errors"]}
                else:
                    print("      Running browser smoke + interaction tests...", flush=True)
                    result = verify_repeated(candidate, plan_path, attempt_dir / "evidence",
                                      timeout=min(test_timeout, remaining), headful=headful,
                                      repeats=verify_repeats, verifier=verifier)
                trace.save(f"attempts/{round_number:02d}/raw_verification.json", result)
                if result.get("smoke", {}).get("passed") and summary["first_playable_seconds"] is None:
                    summary["first_playable_seconds"] = round(time.monotonic() - started, 3)
                if (summary["planning_status"] == "failed_startup_only" and
                        not summary["planning_recovery_attempted"] and
                        result.get("smoke", {}).get("passed") and
                        not result.get("runtime_errors") and not result.get("infrastructure_error")):
                    # A single bounded recovery. The benchmark's held-out checks are never inputs.
                    if client.calls < max_calls and deadline - time.monotonic() >= 15:
                        summary["planning_recovery_attempted"] = True
                        trace.event("plan_recovery_start", remaining_calls=max_calls - client.calls)
                        try:
                            recovered_raw = client.ask_json("plan_recovery", planning_system, json.dumps({
                                "original_spec": spec, "previous_plan": raw_plan,
                                "validation_feedback": plan_error, "recovery_mode": True,
                                "execution_contract": EXECUTION_CONTRACT,
                                "instruction": "Repair the functional plan against the original spec. Do not weaken earlier requirements or assertions. No game implementation or held-out checks are supplied."}, ensure_ascii=False))
                            trace.save("recovery_response.json", recovered_raw)
                            recovered = validate_recovery(raw_plan, recovered_raw)
                        except Exception as error:
                            # Preserve the already generated game if recovery/API/budget fails.
                            summary["planning_recovery_error"] = trace.redact(str(error))
                            trace.event("plan_recovery_failed", error=summary["planning_recovery_error"])
                        else:
                            if plan_path.read_bytes() != plan_bytes:
                                raise RuntimeError("Frozen startup plan changed unexpectedly")
                            plan = recovered
                            plan_path, plan_bytes, plan_hash = record_plan(trace, plan, "functional_plan.json")
                            summary.update(planning_status="recovered", planning_recovered=True,
                                           plan_sha256=plan_hash, active_plan=plan_path.name, gameplay=plan.get("gameplay"),
                                           plan_warnings=plan_warnings(plan), plan_quality=review_plan(plan))
                            summary["plan_review"] = inspect_plan(plan, spec)
                            trace.save("functional_plan_review.json", summary["plan_quality"])
                            trace.event("plan_recovered", plan_sha256=plan_hash,
                                        decision="New functional checks frozen before repair; startup results are not reused")
                            # Never compare a new functional score with an older startup-only score.
                            best, best_bundle = None, None
                            state.tested_hashes.clear()
                            remaining = deadline - time.monotonic()
                            result = (verify_repeated(candidate, plan_path, attempt_dir / "functional_evidence",
                                               timeout=min(test_timeout, remaining), headful=headful,
                                               repeats=verify_repeats, verifier=verifier)
                                      if remaining > 0 else {
                                          "ok": False, "smoke": {"passed": False}, "tests": [],
                                          "runtime_errors": [], "infrastructure_error": "Budget exhausted before functional verification"})
                            trace.save(f"attempts/{round_number:02d}/raw_functional_verification.json", result)
                    else:
                        trace.event("plan_recovery_skipped", reason="Insufficient remaining API/time budget")
                if plan_path.read_bytes() != plan_bytes:
                    raise RuntimeError("Frozen plan changed during verification; refusing completion")
                result = apply_gate(plan, result, summary["planning_status"])
                fingerprint = failure_fingerprint(result)
                current_failure = (plan_hash, fingerprint) if fingerprint else None
                identical_failures = identical_failures + 1 if current_failure and current_failure == last_failure else (1 if current_failure else 0)
                last_failure = current_failure
                result["repair_route"] = route_failure(result, summary["plan_review"], identical_failures >= 2)
                trace.save(f"attempts/{round_number:02d}/verification.json", result)
                elapsed = round(time.monotonic() - started, 3)
                entry = {"round": round_number, "bundle_valid": True,
                         "failure_summary": failure_summary(result),
                         "automated_checks_passed": bool(result.get("ok")),
                         "smoke_passed": bool(result.get("smoke", {}).get("passed")),
                         "tests_passed": sum(bool(t.get("passed")) for t in result.get("tests", [])),
                         "tests_total": len(plan["tests"]), "elapsed_seconds": elapsed,
                         "plan_sha256": plan_hash, "quality_gate": result["quality_gate"],
                         "edit": edit_info, "artifacts_passed": artifacts["ok"],
                         "reliability": result.get("reliability"),
                         "identical_assertion_failures": identical_failures,
                         "infrastructure_error": result.get("infrastructure_error")}
                summary["attempts"].append(entry)
                state.observe(round_number, digest, result, bundle.get("summary", ""), plan_hash)
                trace.event("verification", **entry, decision=str(bundle.get("summary", ""))[:2000])
                preferable, regressions = prefer_candidate(best[1], result) if best else (True, [])
                entry["regressed_test_ids"] = regressions
                if preferable:
                    best = (candidate, result, round_number)
                    best_bundle = bundle
                    state.best_round = round_number
                if regressions:
                    trace.event("regression_preserved_base", round=round_number, test_ids=regressions)
                trace.save("state.json", {**state.context(), "active_plan": plan_path.name,
                           "plan_sha256": plan_hash, "candidate": str(candidate.relative_to(output)),
                           "remaining_calls": max(0, max_calls - client.calls),
                           "remaining_seconds": max(0, round(deadline - time.monotonic(), 3))})
                # Repair from the strongest observed base, not a later broken rewrite.
                previous = best_bundle
                if summary["planning_status"] == "failed_startup_only":
                    summary["had_verification_failure"] = result.get("verifier_ok") is not True
                    state.stop_reason = "startup_only_functional_acceptance_unverified"
                    break
                if not result["quality_gate"]["functional_evidence_present"]:
                    state.stop_reason = "functional_evidence_missing"
                    break
                if result.get("ok"):
                    state.stop_reason = "automated_checks_passed"
                    summary["recovered_after_verification_failure"] = summary["had_verification_failure"]
                    break
                route = result["repair_route"]
                summary["last_repair_route"] = route
                if route["action"] == "stop_infrastructure":
                    # Browser infrastructure failure is not fixed by rewriting game logic.
                    summary["error"] = result["infrastructure_error"]
                    state.stop_reason = "infrastructure_error"
                    break
                if route["action"] == "stop_unverified":
                    state.stop_reason = "verification_evidence_incomplete"
                    break
                if route["action"] == "stop_test_review":
                    state.stop_reason = "plan_review_required"
                    summary["had_verification_failure"] = True
                    break
                summary["had_verification_failure"] = True
                if (diagnose_failures and not diagnosis_attempted and route["action"] == "review_failure"
                        and max_calls - client.calls >= 2 and deadline - time.monotonic() >= 15
                        and round_number < max_rounds):
                    diagnosis_attempted = True
                    raw_diagnosis = client.ask_json("diagnose", DIAGNOSTIC_SYSTEM, json.dumps({
                        "original_spec": spec, "frozen_plan": plan,
                        "source": best_bundle, "evidence": best[1]}, ensure_ascii=False))
                    try:
                        diagnosis = validate_diagnosis(raw_diagnosis, best[1])
                    except ValueError as error:
                        trace.event("diagnosis_rejected", error=str(error))
                    else:
                        trace.save("diagnosis.json", diagnosis)
                        best[1]["diagnosis"] = diagnosis
                        summary["diagnosis"] = diagnosis
                        if diagnosis["category"] in {"test_issue", "tool_limit", "uncertain"}:
                            state.stop_reason = "diagnosis_unverified"
                            break
                feedback = best[1]
            if best:
                chosen, result, chosen_round = best
                shutil.copytree(chosen, output / "game")
                summary.update(selected_round=chosen_round,
                               automated_checks_passed=bool(result.get("ok")), quality_gate=result["quality_gate"],
                               infrastructure_checks_passed=bool(result.get("smoke", {}).get("passed")) and not result.get("runtime_errors"),
                               smoke_passed=bool(result.get("smoke", {}).get("passed")),
                               runtime_error_count=len(result.get("runtime_errors", [])),
                               requirements=requirement_results(plan, result),
                               manual_checks=plan.get("manual_checks", []))
                summary["failure_summary"] = failure_summary(result)
                reqs = summary["requirements"]
                automated = [r for r in reqs if r["verification"] == "automated"]
                summary["automated_requirement_pass_rate"] = (
                    sum(r["status"] == "automated_pass" for r in automated) / len(automated) if automated else None)
                summary["status"] = "automated_passed_manual_pending" if result.get("ok") else "checks_failed"
                exit_code = 0 if result.get("ok") else 2
                if summary["planning_status"] == "failed_startup_only":
                    summary.update(status="partial_game_plan_failed", automated_checks_passed=False,
                                   automated_requirement_pass_rate=None)
                    exit_code = 2
                elif not result["quality_gate"]["functional_evidence_present"]:
                    summary.update(status="partial_game_evidence_missing", automated_checks_passed=False)
                    exit_code = 2
                elif state.stop_reason in {"plan_review_required", "diagnosis_unverified"}:
                    summary.update(status="plan_review_required", automated_checks_passed=False)
                    exit_code = 2
                if lessons_enabled and result.get("ok"):
                    try:
                        summary["lessons_recorded"] = record_recovery(lessons_path, lesson_store, state.repair_memory,
                            result, bundle_digest(best_bundle), plan_hash, trace.redact(output.name))
                    except (OSError, ValueError, TypeError) as error:
                        trace.event("lessons_not_saved", reason=trace.redact(str(error)))
            else:
                summary.update(status="generation_failed", error="No valid game bundle produced")
                exit_code = 2
    except (Exception, KeyboardInterrupt) as error:
        status = "interrupted" if isinstance(error, KeyboardInterrupt) else (
            "budget_exhausted" if isinstance(error, BudgetError) else
            "plan_review_required" if isinstance(error, PlanReviewError) else "run_error")
        summary.update(status=status,
                       error=trace.redact(str(error)))
        trace.event("run_error", error=summary["error"])
        if best and not (output / "game").exists():
            shutil.copytree(best[0], output / "game")
            summary.update(selected_round=best[2], smoke_passed=bool(best[1].get("smoke", {}).get("passed")),
                           runtime_error_count=len(best[1].get("runtime_errors", [])),
                           infrastructure_checks_passed=bool(best[1].get("smoke", {}).get("passed")) and not best[1].get("runtime_errors"),
                           requirements=requirement_results(plan, best[1]),
                           manual_checks=plan.get("manual_checks", []))
            summary["quality_gate"] = best[1].get("quality_gate")
            summary["failure_summary"] = failure_summary(best[1])
        elif pending_candidate is not None and not (output / "game").exists():
            shutil.copytree(pending_candidate, output / "game")
            summary["preserved_unverified_candidate"] = True
        exit_code = 130 if isinstance(error, KeyboardInterrupt) else (2 if isinstance(error, PlanReviewError) else 4)
    finally:
        summary["settings_sha256"] = hashlib.sha256(json.dumps(summary["features"], sort_keys=True).encode()).hexdigest()
        summary["stop_reason"] = state.stop_reason or summary.get("status")
        trace.save("state.json", {**state.context(), "stop_reason": summary["stop_reason"],
                   "active_plan": str(plan_path.name) if plan is not None and 'plan_path' in locals() else None,
                   "plan_sha256": summary.get("plan_sha256"),
                   "selected_candidate": str(best[0].relative_to(output)) if best else None,
                   "remaining_calls": max(0, max_calls - client.calls),
                   "remaining_seconds": max(0, round(deadline - time.monotonic(), 3)),
                   "note": "Audit checkpoint only; automatic process resume is not implemented."})
        summary["duration_seconds"] = round(time.monotonic() - started, 3)
        summary["usage"] = client.usage_summary()
        summary["first_playable_metric_note"] = "Time to first visible smoke-passing version; not full acceptance."
        trace.event("run_end", status=summary["status"], duration_seconds=summary["duration_seconds"])
        trace.save("summary.json", summary)
        (output / "summary.json").write_text(trace.redact(json.dumps(summary, ensure_ascii=False, indent=2)), encoding="utf-8")
        write_report(output, summary)
        print(f"[4/4] {summary['status']}\nResults: {output.resolve()}", flush=True)
        if (output / "game").is_dir():
            print(f'Play: python -m agent serve "{output.resolve() / "game"}"', flush=True)
    return exit_code


def write_report(output, summary):
    usage = summary["usage"]
    lines = ["# PlayForge — 自动开发运行报告", "", f"- 状态：`{summary['status']}`",
             f"- 模型：`{summary['model']}`", f"- 耗时：{summary['duration_seconds']} 秒",
             f"- API 尝试次数：{usage['api_attempts']}",
             f"- 已知输入 / 输出 token：{usage['prompt_tokens']} / {usage['completion_tokens']}",
             f"- 用量未知的调用次数：{usage['calls_with_unknown_usage']}",
             f"- 已知用量估算费用：{usage['estimated_known_usage_cost']} {usage['currency']}", "",
             "自动通过不等于完整验收；None 表示未测量或未配置价格，不是零。", "",
             "## 需求与自动检查", ""]
    for item in summary.get("requirements", []):
        lines.append(f"- {item['id']} [{item['status']}] {item['text']}")
    lines += ["", "## 测试诊断与计划提醒", "",
              f"- Agent 版本：{summary.get('agent_version', 'unknown')}",
              f"- 停止原因：{summary.get('stop_reason')}",
              f"- 规划状态：{summary.get('planning_status')}",
              f"- 冻结前模型审查：{summary.get('plan_audit_status', 'not_requested')}",
              f"- 功能规划恢复成功：{summary.get('planning_recovered', False)}",
              f"- 完成门禁：{json.dumps(summary.get('quality_gate'), ensure_ascii=False)}",
              f"- 玩法分析：{json.dumps(summary.get('gameplay'), ensure_ascii=False)}",
              f"- 自动需求通过比例：{summary.get('automated_requirement_pass_rate')}",
              f"- 失败分类：{json.dumps(summary.get('failure_summary', {}).get('counts', {}), ensure_ascii=False)}",
              f"- 建议复核的测试：{summary.get('failure_summary', {}).get('review_test_ids', [])}", "",
              "目标超时、断言不符不直接证明游戏代码错误，也可能是操作策略或测试计划问题。失败不会因此自动算通过。"]
    if summary.get("planning_status") == "failed_startup_only":
        lines += ["", "规划未通过；当前只检查启动，不声称原始功能已验收。",
                  "规划错误：" + str(summary.get("planning_error", ""))]
    for warning in summary.get("plan_warnings", []):
        lines.append(f"- {warning['test_id']}: {warning['message']}")
    for warning in summary.get("plan_quality", {}).get("warnings", []):
        lines.append(f"- 计划质量提醒 {warning['test_id']}: {warning['message']}")
    for warning in summary.get("plan_review", {}).get("warnings", []):
        lines.append(f"- 测试计划复核 {warning['test_id']}: {warning['message']}")
    lines += ["", "## 人工试玩待办", "", "- [ ] 根据原始需求完整试玩，检查自动测试遗漏和状态钩子的真实性。"]
    for check in summary.get("manual_checks", []):
        lines.append(f"- [ ] {check['requirement_id']}: {check['instruction']}")
    if summary.get("error"):
        lines += ["", "## 未完成或错误", "", summary["error"]]
    if (output / "game" / "index.html").is_file():
        lines += ["", "## 启动游戏", "", "在 PlayForge 项目目录运行：", "", "```powershell",
                  f'python -m agent serve "{output.resolve() / "game"}"', "```"]
    else:
        lines += ["", "本次未生成可启动游戏；请先查看上述停止原因及 traces/ 中的计划／审查记录。"]
    lines += ["", "原始需求、已保存的计划、API 用量及可用的执行证据位于 traces/。", "",
              "计价依赖用户配置；失败/超时请求也可能计费，以服务商账单为准。"]
    (output / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
