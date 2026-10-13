"""Cheap artifact checks; no generated host code or arbitrary command execution."""
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
import posixpath
import shutil
import subprocess
from urllib.parse import unquote, urlsplit

from .verification import child_environment


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        attribute = "href" if tag == "link" else "src"
        if tag in {"script", "link", "img", "audio", "video", "source", "iframe"} and values.get(attribute):
            self.items.append((tag, values[attribute]))


def check_artifacts(game: Path, syntax=False, timeout=5):
    errors = []
    for file in sorted(game.rglob("*.html")):
        parser = References()
        parser.feed(file.read_text(encoding="utf-8-sig"))
        for tag, value in parser.items:
            parts = urlsplit(value)
            if parts.scheme == "data" and tag == "img":
                continue
            if parts.scheme or parts.netloc:
                errors.append({"file": file.relative_to(game).as_posix(), "reference": value[:300],
                               "error": "External resource is outside offline scope"})
                continue
            path = unquote(parts.path)
            if not path:
                continue
            relative = posixpath.normpath(path.lstrip("/") if path.startswith("/") else
                                         posixpath.join(file.relative_to(game).parent.as_posix(), path))
            target = game.joinpath(*PurePosixPath(relative).parts)
            if "\\" in path or not target.resolve().is_relative_to(game.resolve()) or not target.is_file():
                errors.append({"file": file.relative_to(game).as_posix(), "reference": value[:300],
                               "error": "Missing or out-of-project local resource"})
    syntax_result = {"status": "not_requested"}
    if syntax:
        node = shutil.which("node")
        syntax_result = {"status": "not_available" if not node else "checked_external_js", "files": []}
        if node:
            env = child_environment()
            env.pop("NODE_OPTIONS", None)
            env.pop("NODE_PATH", None)
            import time
            deadline = time.monotonic() + max(0.1, timeout)
            for file in sorted(game.rglob("*.js")):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    syntax_result["status"] = "incomplete_timeout"
                    break
                try:
                    process = subprocess.run([node, "--check", str(file.resolve())], env=env,
                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=remaining)
                except subprocess.TimeoutExpired:
                    syntax_result["status"] = "incomplete_timeout"
                    break
                syntax_result["files"].append(file.relative_to(game).as_posix())
                if process.returncode:
                    errors.append({"file": file.relative_to(game).as_posix(), "error": "JavaScript syntax error",
                                   "detail": process.stderr[-1500:]})
    return {"ok": not errors, "errors": errors, "syntax": syntax_result,
            "note": "Local HTML resource references and optional external-JS syntax only; not CSS/import resolution or gameplay validation."}
