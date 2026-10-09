"""Configuration only: no key is ever included in model prompts or run metadata."""
from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import urlsplit


def load_dotenv(path: Path) -> None:
    """Small non-executing dotenv reader; existing environment variables win."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, sep, value = line.partition("=")
        if not sep or not name.strip().replace("_", "").isalnum():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(name.strip(), value)


def optional_number(name: str):
    value = os.getenv(name, "").strip()
    if not value:
        return None
    number = float(value)
    if not (0 <= number < float("inf")):
        raise ValueError(f"{name} must be a finite nonnegative number")
    return number


@dataclass(frozen=True)
class Config:
    api_key: str
    base_url: str
    model: str
    thinking: str
    json_mode: bool
    max_tokens: int
    timeout: float
    input_price: float | None
    cached_price: float | None
    output_price: float | None
    currency: str

    @classmethod
    def from_env(cls):
        base = os.getenv("LLM_BASE_URL", "https://api.deepseek.com").rstrip("/")
        url = urlsplit(base)
        local_http = url.scheme == "http" and url.hostname in {"127.0.0.1", "localhost"}
        if url.username or url.password or url.query or url.fragment or not url.hostname:
            raise ValueError("LLM_BASE_URL must be a clean API base URL")
        if url.scheme != "https" and not local_http:
            raise ValueError("API key may only be sent over HTTPS (or explicit localhost HTTP)")
        thinking = os.getenv("LLM_THINKING", "disabled").strip()
        if thinking not in {"", "enabled", "disabled"}:
            raise ValueError("LLM_THINKING must be disabled, enabled, or blank")
        max_tokens = int(os.getenv("LLM_MAX_TOKENS", "12000"))
        timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "90"))
        if not 1024 <= max_tokens <= 32000 or not 1 <= timeout <= 300:
            raise ValueError("max_tokens must be 1024..32000; timeout must be 1..300")
        return cls(
            os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY", ""), base,
            os.getenv("LLM_MODEL", "deepseek-flash"), thinking,
            os.getenv("LLM_JSON_MODE", "true").lower() == "true", max_tokens, timeout,
            optional_number("PRICE_INPUT_PER_MILLION"),
            optional_number("PRICE_CACHED_INPUT_PER_MILLION"),
            optional_number("PRICE_OUTPUT_PER_MILLION"),
            os.getenv("PRICE_CURRENCY", "USD"),
        )
