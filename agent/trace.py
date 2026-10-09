"""Append-only controller records, with explicit redaction of the configured key."""
import json
from datetime import datetime, timezone
from pathlib import Path


class Trace:
    def __init__(self, root: Path, secrets=()):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.secrets = tuple(s for s in secrets if s)

    def redact(self, text: str) -> str:
        for secret in self.secrets:
            text = text.replace(secret, "[REDACTED]")
        return text

    def save(self, name: str, data):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
        target.write_text(self.redact(payload), encoding="utf-8")

    def event(self, kind: str, **fields):
        record = {"time_utc": datetime.now(timezone.utc).isoformat(), "event": kind, **fields}
        with (self.root / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(self.redact(json.dumps(record, ensure_ascii=False, allow_nan=False)) + "\n")
