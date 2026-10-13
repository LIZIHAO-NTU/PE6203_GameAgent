"""Minimal chat-completions adapter; no vendor SDK and no existing coding agent."""
import json
import base64
import io
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request


class ProviderError(RuntimeError):
    pass


class BudgetError(ProviderError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward bearer credentials to a redirect target.
        return None


def open_request(request, timeout):
    # A subprocess supplies a whole-request deadline, not just socket inactivity timeouts.
    # The key travels via stdin, never argv, generated code, disk, or browser environment.
    from .verification import child_environment, stop_worker
    payload = {"url": request.full_url, "body": base64.b64encode(request.data).decode("ascii"),
               "headers": dict(request.header_items()), "timeout": timeout}
    process = subprocess.Popen([sys.executable, "-B", "-m", "agent.http_worker"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=child_environment(), cwd=Path(__file__).resolve().parent.parent,
        start_new_session=sys.platform != "win32")
    try:
        stdout, _ = process.communicate(json.dumps(payload).encode("utf-8"), timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        stop_worker(process)
        if isinstance(error, KeyboardInterrupt):
            raise
        raise TimeoutError("Whole API request deadline exceeded") from None
    try:
        result = json.loads(stdout)
    except (ValueError, UnicodeError):
        raise urllib.error.URLError("HTTP worker failed without a valid response") from None
    if result.get("kind") == "http_error":
        raise urllib.error.HTTPError(request.full_url, result["status"], "API HTTP error", {}, None)
    if result.get("kind") != "ok":
        raise urllib.error.URLError(result.get("kind", "transport_error"))
    return io.BytesIO(base64.b64decode(result["body"]))


def parse_json_object(content: str) -> dict:
    text = content.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    value = json.loads(text, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    if not isinstance(value, dict):
        raise ValueError("Expected one JSON object, not a list or prose")
    return value


class ChatClient:
    def __init__(self, config, trace, max_calls: int, deadline: float):
        self.config, self.trace = config, trace
        self.max_calls, self.deadline = max_calls, deadline
        self.calls = 0
        self.prompt_tokens = self.completion_tokens = self.cached_tokens = 0
        self.unknown_usage_calls = 0

    def ask_json(self, stage: str, system: str, prompt: str) -> dict:
        # One retry for transient transport / formatting failures. All attempts consume budget.
        last_error = None
        attempts = 1 if stage == "diagnose" else 2
        for attempt in range(attempts):
            if self.calls >= self.max_calls or time.monotonic() >= self.deadline:
                raise BudgetError("API call/time budget reached")
            self.calls += 1
            number = self.calls
            body = {"model": self.config.model, "messages": [
                {"role": "system", "content": system}, {"role": "user", "content": prompt}],
                "max_tokens": min(2000 if stage == "diagnose" else 6000, self.config.max_tokens)
                              if stage.startswith("plan") or stage == "diagnose" else self.config.max_tokens,
                "stream": False}
            if self.config.json_mode:
                body["response_format"] = {"type": "json_object"}
            if self.config.thinking:
                body["thinking"] = {"type": self.config.thinking}
            self.trace.save(f"api/{number:03d}_request.json", {"stage": stage, **body})
            self.trace.event("api_start", call=number, stage=stage, retry=attempt)
            req = urllib.request.Request(self.config.base_url + "/chat/completions",
                data=json.dumps(body).encode("utf-8"),
                headers={"Authorization": "Bearer " + self.config.api_key,
                         "Content-Type": "application/json"}, method="POST")
            started = time.monotonic()
            response_received = False
            usage_known = False
            retryable = True
            try:
                timeout = min(self.config.timeout, max(0.1, self.deadline - started))
                with open_request(req, timeout=timeout) as response:
                    raw = response.read(3_000_001)
                response_received = True
                if len(raw) > 3_000_000:
                    raise ValueError("API response exceeded local size limit")
                data = json.loads(raw)
                usage = data.get("usage") or {}
                if "prompt_tokens" in usage and "completion_tokens" in usage:
                    prompt_tokens = int(usage["prompt_tokens"])
                    completion_tokens = int(usage["completion_tokens"])
                    cached = usage.get("prompt_cache_hit_tokens", usage.get("prompt_tokens_details", {}).get("cached_tokens", 0))
                    cached_tokens = max(0, min(int(cached or 0), prompt_tokens))
                    if prompt_tokens < 0 or completion_tokens < 0:
                        raise ValueError("Invalid negative API usage")
                    self.prompt_tokens += prompt_tokens
                    self.completion_tokens += completion_tokens
                    self.cached_tokens += cached_tokens
                    usage_known = True
                self.trace.save(f"api/{number:03d}_response.json", data)
                choice = data["choices"][0]
                if choice.get("finish_reason") == "length":
                    raise ValueError("Output truncated: increase LLM_MAX_TOKENS or reduce scope")
                content = choice["message"].get("content") or ""
                result = parse_json_object(content)
                self.trace.event("api_ok", call=number, stage=stage, usage=usage,
                                 duration_seconds=round(time.monotonic() - started, 3))
                return result
            except urllib.error.HTTPError as error:
                # Do not print response bodies: a gateway can echo credentials.
                retryable = error.code in {408, 429, 500, 502, 503, 504}
                last_error = f"API HTTP {error.code}; check account/model/configuration"
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                last_error = f"API transport failure: {type(error).__name__}"
            except (ValueError, KeyError, IndexError, TypeError) as error:
                last_error = f"Invalid API/JSON response: {error}"
            finally:
                if not usage_known:
                    self.unknown_usage_calls += 1
            self.trace.event("api_error", call=number, stage=stage, error=str(last_error),
                             response_received=response_received, retryable=retryable)
            if not retryable or attempt == attempts - 1:
                break
            remaining = self.deadline - time.monotonic()
            if remaining > 1:
                time.sleep(min(2, remaining))
        raise ProviderError(str(last_error))

    def usage_summary(self):
        c = self.config
        estimate = None
        if c.input_price is not None and c.output_price is not None:
            cached_rate = c.cached_price if c.cached_price is not None else c.input_price
            estimate = ((self.prompt_tokens - self.cached_tokens) * c.input_price
                        + self.cached_tokens * cached_rate
                        + self.completion_tokens * c.output_price) / 1_000_000
        return {"api_attempts": self.calls, "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens, "cached_input_tokens": self.cached_tokens,
                "calls_with_unknown_usage": self.unknown_usage_calls,
                "estimated_known_usage_cost": estimate, "currency": c.currency,
                "cost_is_complete": estimate is not None and self.unknown_usage_calls == 0,
                "note": "User-supplied rates only; not a billing statement. Unknown calls may be billed."}
