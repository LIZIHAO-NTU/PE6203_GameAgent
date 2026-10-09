"""Explicit launch-only degradation; never silently weaken functional acceptance."""


def startup_only_plan():
    # Generic infrastructure, not a prewritten game or a substitute functional test suite.
    return {"supported": True, "reason": "", "title": "Partial game: functional plan unavailable",
        "development_plan": ["Implement all mandatory original-spec rules in a small runnable game",
                             "Validate startup; leave functional acceptance explicitly unverified"],
        "state_contract": {"phase": "Actual current game phase, read-only"},
        "requirements": [
            {"id": "Startup", "text": "Visible local game surface and error-free browser startup only",
             "verification": "automated", "priority": "core"},
            {"id": "OriginalRules", "text": "ALL mandatory functional and technical requirements in original_spec",
             "verification": "manual", "priority": "core"}],
        "tests": [{"id": "StartupSurface", "requirement_ids": ["Startup"],
                   "description": "Infrastructure only; does not check game rules",
                   "steps": [{"action": "assert", "source": "count",
                              "selector": "canvas, [data-game-surface]", "op": "ge", "value": 1}]}],
        "manual_checks": [{"requirement_id": "OriginalRules",
                           "instruction": "Verify every original-spec rule and technical constraint; no functional acceptance is claimed."}]}
