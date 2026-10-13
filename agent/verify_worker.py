"""Browser verifier. Only the trusted DSL is executed; no model-supplied Python."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit

from .contracts import compare, lookup, validate_plan
from .server import running_server
from .evidence import file_hashes, runtime_metadata


def launch(browser_type, headful=False):
    options = {"headless": not headful, "chromium_sandbox": True}
    channel = os.getenv("PLAYWRIGHT_CHANNEL", "").strip()
    if channel:
        options["channel"] = channel
    return browser_type.launch(**options)


def fresh_page(browser, origin, errors, label):
    context = browser.new_context(viewport={"width": 1000, "height": 760},
                                  accept_downloads=False, service_workers="block")

    def route_request(route):
        url = route.request.url
        parts = urlsplit(url)
        actual_origin = f"{parts.scheme}://{parts.netloc}"
        if actual_origin == origin:
            route.continue_()
        else:
            if len(errors) < 40:
                errors.append({"phase": label, "error": "Blocked nonlocal request: " + url[:300]})
            route.abort()

    context.route("**/*", route_request)
    page = context.new_page()
    page.set_default_timeout(1200)
    page.set_default_navigation_timeout(6000)

    def record(message):
        if len(errors) < 40:
            errors.append({"phase": label, "error": str(message)[:1000]})

    page.on("pageerror", record)
    page.on("console", lambda message: record(message.text) if message.type == "error" else None)
    page.on("response", lambda response: record(f"HTTP {response.status}: {response.url}")
            if response.status >= 400 else None)

    def dialog_handler(dialog):
        record("Unexpected dialog: " + dialog.message[:300])
        dialog.dismiss()

    page.on("dialog", dialog_handler)
    page.goto(origin + "/", wait_until="load")
    page.wait_for_timeout(150)
    return context, page


def state_snapshot(page):
    state = page.evaluate("""() => {
        if (!window.__gameTest || typeof window.__gameTest.getState !== 'function')
            throw new Error('Missing read-only window.__gameTest.getState()');
        return JSON.parse(JSON.stringify(window.__gameTest.getState()));
    }""")
    if not isinstance(state, dict) or len(json.dumps(state, allow_nan=False)) > 64000:
        raise ValueError("State hook must return a small plain JSON object")
    return state


def smoke_check(page):
    # Independent of the game's test hook: check visible render surface and canvas pixels.
    return page.evaluate("""() => {
      const surfaces = [...document.querySelectorAll('canvas, [data-game-surface]')];
      const visible = surfaces.filter(e => {const r=e.getBoundingClientRect();
        const s=getComputedStyle(e); return r.width>=80 && r.height>=80 &&
          s.display!=='none' && s.visibility!=='hidden' && Number(s.opacity)>0;});
      if (!visible.length) return {passed:false, reason:'No visible game surface >=80x80'};
      const canvas = visible.find(e => e.tagName==='CANVAS');
      if (canvas) {
        const ctx = canvas.getContext('2d');
        if (!ctx) return {passed:false, reason:'MVP verifier expects a 2D canvas'};
        const p=ctx.getImageData(0,0,canvas.width,canvas.height).data;
        let diverse=false;
        for(let i=4;i<p.length;i+=4) {
          if(p[i]!==p[0] || p[i+1]!==p[1] || p[i+2]!==p[2] || p[i+3]!==p[3]) {diverse=true;break;}
        }
        if(!diverse) return {passed:false, reason:'Canvas is blank/uniform'};
      }
      return {passed:true, reason:'Visible rendered surface; not proof of correct gameplay',
              title:document.title};
    }""")


def observe_condition(page, condition, captures, state=None):
    source = condition["source"]
    if source == "state":
        actual = lookup(state if state is not None else state_snapshot(page), condition["path"])
    elif source == "text":
        actual = page.locator(condition["selector"]).inner_text()[:4000]
    elif source == "visible":
        actual = page.locator(condition["selector"]).is_visible()
    elif source == "count":
        actual = page.locator(condition["selector"]).count()
    elif source == "enabled":
        actual = page.locator(condition["selector"]).is_enabled()
    elif source == "attribute":
        actual = page.locator(condition["selector"]).get_attribute(condition["attribute"])
    else:
        # Fixed trusted code; measures the DOM surface independently of the state hook.
        measures = page.locator(condition["selector"]).evaluate("""e => {
            const r=e.getBoundingClientRect();
            return {width:e.width ?? r.width, height:e.height ?? r.height,
                    css_width:r.width, css_height:r.height};
        }""")
        actual = measures[condition["property"]]
    ref = condition.get("value_from")
    expected = lookup(captures[ref["capture"]], ref["path"]) if ref else condition["value"]
    return {"actual": actual, "op": condition["op"], "expected": expected,
            "passed": bool(compare(actual, condition["op"], expected))}


def observe_consistency(page, step):
    expected = lookup(state_snapshot(page), step["state_path"])
    observation = observe_condition(page, {**step, "op": "eq", "value": expected}, {})
    actual = observation["actual"]
    if step.get("coerce", "none") == "number":
        if isinstance(actual, bool) or not isinstance(actual, (str, int, float)):
            raise ValueError("DOM value is not a numeric scalar")
        actual = float(actual)
        if not math.isfinite(actual):
            raise ValueError("DOM number is not finite")
    return {**observation, "actual": actual,
            "passed": bool(compare(actual, "eq", expected)), "state_path": step["state_path"]}


def pointer_target(page, step, position=None):
    """Resolve coordinates from the actual rendered element, never mutate game state."""
    locator = page.locator(step["selector"])
    locator.scroll_into_view_if_needed()
    box = locator.bounding_box()
    if not box:
        raise ValueError("Pointer target is not visible")
    position = position or step.get("position")
    if position is None:
        return locator, {"x": box["width"] / 2, "y": box["height"] / 2}, box
    local = dict(position)
    if step.get("coordinate_space", "css") == "canvas":
        dimensions = locator.evaluate("e => ({width:e.width, height:e.height, tag:e.tagName})")
        if dimensions["tag"] != "CANVAS" or not dimensions["width"] or not dimensions["height"]:
            raise ValueError("Canvas coordinates require a nonempty canvas")
        local = {axis: position[axis] * box[size] / dimensions[size]
                 for axis, size in (("x", "width"), ("y", "height"))}
    if not (0 <= local["x"] < box["width"] and 0 <= local["y"] < box["height"]):
        raise ValueError("Pointer position is outside the rendered target")
    return locator, local, box


def run_pointer(page, step):
    locator, local, box = pointer_target(page, step)
    if step["action"] == "click":
        if not locator.is_enabled():
            # A real user cannot activate a disabled control. Observe the no-op; do not
            # force-click, enable it with JS, or turn correct terminal locking into a bug.
            return {"selector": step["selector"], "ignored_disabled": True}
        locator.click(position=local, button=step.get("button", "left"))
    elif step["action"] == "hover":
        locator.hover(position=local)
    else:
        _, end, _ = pointer_target(page, step, step["to"])
        page.mouse.move(box["x"] + local["x"], box["y"] + local["y"])
        page.mouse.down(button=step.get("button", "left"))
        try:
            page.mouse.move(box["x"] + end["x"], box["y"] + end["y"], steps=step.get("steps", 8))
        finally:
            page.mouse.up(button=step.get("button", "left"))
    return {"selector": step["selector"], "position_css": local}


def run_goal(page, step, captures):
    """Bounded feedback control using normal keyboard events, never state setters."""
    started = time.monotonic()
    deadline = started + step.get("timeout_ms", 5000) / 1000
    polls, last_state, first_position, last_position = 0, None, None, None
    while True:
        action = step["action"]
        if action == "move_to" or step["until"]["source"] == "state":
            last_state = state_snapshot(page)
        observation = observe_condition(page, step["until"], captures, last_state)
        polls += 1
        if observation["passed"] or time.monotonic() >= deadline:
            return {**observation, "action": action, "polls": polls,
                    "elapsed_ms": round((time.monotonic() - started) * 1000),
                    "last_state": last_state, "first_position": first_position,
                    "last_position": last_position}
        key = step.get("key") if action == "key_until" else None
        if action == "move_to":
            actor = {axis: lookup(last_state, path) for axis, path in step["actor"].items()}
            target = {axis: lookup(last_state, path) for axis, path in step["target"].items()}
            if not all(type(v) in {int, float} and math.isfinite(v)
                       for v in [*actor.values(), *target.values()]):
                raise ValueError("Navigation coordinates must be finite numbers")
            first_position = first_position or actor
            last_position = actor
            dx, dy = target["x"] - actor["x"], target["y"] - actor["y"]
            tolerance = step.get("tolerance", 4)
            if max(abs(dx), abs(dy)) > tolerance:
                direction = ("right" if dx > 0 else "left") if abs(dx) >= abs(dy) else (
                    "down" if dy > 0 else "up")
                key = step["keys"][direction]
        duration = min(step.get("poll_ms", 50), max(1, (deadline - time.monotonic()) * 1000))
        if key:
            page.keyboard.down(key)
            try:
                page.wait_for_timeout(duration)
            finally:
                page.keyboard.up(key)
        else:
            page.wait_for_timeout(duration)


def run_test(page, test):
    captures, observations, actions = {}, [], []
    for index, step in enumerate(test["steps"], start=1):
        event = {"step": index, "action": step["action"], "arguments": step, "ok": False}
        actions.append(event)
        started = time.monotonic()
        try:
            action = step["action"]
            if action in {"click", "hover", "drag"}:
                event["result"] = run_pointer(page, step)
            elif action == "key":
                hold = step.get("hold_ms", 0)
                if hold:
                    page.keyboard.down(step["key"])
                    try:
                        page.wait_for_timeout(hold)
                    finally:
                        page.keyboard.up(step["key"])
                else:
                    page.keyboard.press(step["key"])
            elif action == "keys":
                held = []
                try:
                    for key in step["keys"]:
                        page.keyboard.down(key)
                        held.append(key)
                    page.wait_for_timeout(step.get("hold_ms", 100))
                finally:
                    for key in reversed(held):
                        page.keyboard.up(key)
            elif action == "wait":
                page.wait_for_timeout(step["ms"])
            elif action == "capture":
                captures[step["name"]] = state_snapshot(page)
                event["result"] = captures[step["name"]]
            elif action == "sample":
                samples = []
                count, duration = step.get("samples", 3), step.get("duration_ms", 500)
                for i in range(count):
                    if i:
                        page.wait_for_timeout(duration / (count - 1))
                    samples.append({"elapsed_ms": round((time.monotonic() - started) * 1000),
                                    "state": state_snapshot(page)})
                captures[step["name"] + "_start"] = samples[0]["state"]
                captures[step["name"] + "_end"] = samples[-1]["state"]
                event["result"] = {"samples": samples}
            elif action in {"wait_until", "key_until", "move_to"}:
                observation = {"step": index, **run_goal(page, step, captures)}
                observations.append(observation)
                if not observation["passed"]:
                    return {"id": test["id"], "passed": False, "failed_step": index,
                            "failure_kind": "goal_timeout", "needs_test_review": True,
                            "error": "Goal not reached within budget; could be game logic, unreachable target or test strategy. Not proof of a game bug.",
                            "observations": observations, "actions": actions}
            elif action in {"assert", "assert_consistent"}:
                observed = (observe_consistency(page, step) if action == "assert_consistent"
                            else observe_condition(page, step, captures))
                observation = {"step": index, **observed}
                observations.append(observation)
                if not observation["passed"]:
                    return {"id": test["id"], "passed": False, "failed_step": index,
                            "failure_kind": "state_dom_mismatch" if action == "assert_consistent" else "assertion_mismatch", "needs_test_review": True,
                            "error": "Assertion did not match requirement", "observations": observations,
                            "actions": actions}
            else:
                raise ValueError("Unsupported action: " + str(action))
            event["ok"] = True
        except Exception as error:
            event["error"] = str(error)[:2000]
            return {"id": test["id"], "passed": False, "failed_step": index,
                    "failure_kind": "state_contract_error" if isinstance(error, (KeyError, IndexError, TypeError, ValueError)) else "interaction_error",
                    "needs_test_review": True,
                    "error": str(error)[:2000], "observations": observations, "actions": actions}
        finally:
            event["elapsed_ms"] = round((time.monotonic() - started) * 1000)
    return {"id": test["id"], "passed": True, "observations": observations, "actions": actions}


def verify_browser(browser, game, plan, evidence):
    evidence.mkdir(parents=True, exist_ok=True)
    errors, tests = [], []
    with running_server(game) as origin:
        context, page = fresh_page(browser, origin, errors, "smoke")
        try:
            smoke = smoke_check(page)
            page.screenshot(path=str(evidence / "smoke.png"))
        finally:
            context.close()
        for test in plan["tests"]:
            context = None
            error_count = len(errors)
            try:
                context, page = fresh_page(browser, origin, errors, test["id"])
                page.screenshot(path=str(evidence / f'{test["id"]}.before.png'))
                result = run_test(page, test)
                page.screenshot(path=str(evidence / f'{test["id"]}.png'))
                result["screenshot"] = f'{test["id"]}.png'
                result["before_screenshot"] = f'{test["id"]}.before.png'
            except Exception as error:
                result = {"id": test["id"], "passed": False, "failure_kind": "browser_error",
                          "error": str(error)[:2000], "observations": []}
            finally:
                if context:
                    context.close()
            if len(errors) > error_count:
                result["passed"] = False
                result["failure_kind"] = "runtime_error"
                result["runtime_errors"] = errors[error_count:]
            tests.append(result)
    ok = smoke["passed"] and bool(tests) and all(t["passed"] for t in tests) and not errors
    result = {"ok": bool(ok), "smoke": smoke, "tests": tests, "runtime_errors": errors,
              "infrastructure_error": None}
    manifest = {"schema_version": 1, "runtime": runtime_metadata(), "browser": browser.version,
                "viewport": {"width": 1000, "height": 760}, "game_sha256": file_hashes(game),
                "plan_content_sha256": hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest(),
                "plan": plan, "result": result,
                "note": "Replay this fixed plan through recheck; real-time scheduling may differ. Screenshots are evidence, not an automated visual verdict."}
    (evidence / "replay.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {**result, "evidence_manifest": "replay.json"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--game", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--headful", action="store_true")
    args = parser.parse_args()
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser = launch(playwright.chromium, args.headful)
            try:
                if args.preflight:
                    result = {"ok": True, "browser_version": browser.version}
                else:
                    plan = validate_plan(json.loads(args.plan.read_text(encoding="utf-8")))
                    result = verify_browser(browser, args.game, plan, args.evidence)
            finally:
                browser.close()
    except Exception as error:
        result = {"ok": False, "infrastructure_error": str(error)[:2500],
                  "smoke": {"passed": False}, "tests": [], "runtime_errors": []}
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
