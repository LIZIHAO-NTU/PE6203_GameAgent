"""Read-only loopback status viewer; never starts model calls or serves raw traces."""
from html import escape
import json
from pathlib import Path
from urllib.parse import urlsplit

from . import __version__
from .server import GameHandler, ThreadingHTTPServer


def read_text(path, limit=1_000_000):
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents) or not path.is_file() or path.stat().st_size > limit:
        raise ValueError("Evidence unavailable, linked or too large")
    return path.read_text(encoding="utf-8")


def snapshot(root):
    root = Path(root).resolve()
    warnings, summary, events = [], {}, []
    if (root / "summary.json").exists():
        try:
            summary = json.loads(read_text(root / "summary.json"))
            if not isinstance(summary, dict):
                raise ValueError("Summary is not an object")
        except (OSError, ValueError):
            summary = {}
            warnings.append("Summary unreadable; results remain unverified.")
    try:
        for line in read_text(root / "traces/events.jsonl", 2_000_000).splitlines()[-12:]:
            try:
                record = json.loads(line)
                if isinstance(record, dict):
                    events.append({key: record.get(key) for key in ("time_utc", "event", "stage", "round")})
            except ValueError:
                continue
    except (OSError, ValueError):
        pass
    status = summary.get("status") or ("running" if events and events[-1].get("event") != "run_end" and not warnings else "unverified")
    game = root / "game"
    has_game = not game.is_symlink() and game.resolve().is_relative_to(root) and (game / "index.html").is_file()
    return {"summary": summary, "status": status, "events": events, "warnings": warnings, "has_game": has_game}


def render_dashboard(root):
    data = snapshot(root)
    summary = data["summary"]
    usage = summary.get("usage") if isinstance(summary.get("usage"), dict) else {}
    labels = {"running": "Running", "started": "Running", "automated_passed_manual_pending": "Selected checks passed — manual review pending",
              "checks_failed": "Checks failed", "plan_review_required": "Plan review required", "unverified": "Unverified"}
    label = labels.get(data["status"], str(data["status"]))
    rows = []
    requirements = summary.get("requirements", [])
    for requirement in requirements[:12] if isinstance(requirements, list) else []:
        if isinstance(requirement, dict):
            rows.append("<tr>" + "".join("<td>" + escape(str(requirement.get(key, ""))) + "</td>"
                                          for key in ("id", "text", "status")) + "</tr>")
    timeline = "".join("<li><span>" + escape(str(event.get("time_utc", ""))) + "</span> "
                       + escape(str(event.get("event", ""))) + " "
                       + escape(str(event.get("stage") or event.get("round") or "")) + "</li>" for event in data["events"])
    links = '<a class="button" href="/game/" target="_blank" rel="noopener">Open game</a>' if data["has_game"] else '<span>No game artifact yet</span>'
    links += ' <a class="button secondary" href="/report">Read report</a>' if (Path(root) / "REPORT.md").is_file() else ""
    warning = " ".join(data["warnings"])
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="refresh" content="5">
<title>PlayForge — Run status</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f4f6fa;color:#172339;font:16px/1.55 system-ui,sans-serif}}
main{{max-width:1060px;margin:0 auto;padding:32px 20px}}header{{border-bottom:1px solid #d9e0ea;padding-bottom:20px}}
.brand{{font-weight:700;color:#2057a5;letter-spacing:.04em}}h1{{font-size:28px;margin:8px 0}}h2{{font-size:19px}}
.muted{{color:#526175}}.status{{padding:14px 18px;border-left:4px solid #3671b8;background:#e8f0fc;margin:24px 0;font-weight:600}}
.metrics{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}}.metric{{background:#fff;border:1px solid #dde3ec;border-radius:10px;padding:18px}}
.metric strong{{display:block;font-size:24px}}.actions{{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:22px 0}}
.button{{display:inline-block;background:#2057a5;color:#fff;text-decoration:none;padding:10px 17px;border-radius:7px}}
.secondary{{background:#fff;color:#2057a5;border:1px solid #bac9df}}a:focus-visible{{outline:3px solid #bd6c00;outline-offset:3px}}
section{{margin-top:28px}}table{{width:100%;border-collapse:collapse;background:#fff;table-layout:fixed}}th,td{{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid #e2e6ed;overflow-wrap:anywhere}}th:first-child{{width:11%}}th:last-child{{width:25%}}
li{{overflow-wrap:anywhere;margin-bottom:8px}}li span{{color:#526175}}.warning{{color:#943a15}}footer{{margin-top:32px;color:#526175}}
@media(max-width:540px){{.metrics{{grid-template-columns:1fr}}main{{padding:20px 14px}}h1{{font-size:23px}}th,td{{padding:8px;font-size:14px}}}}
</style></head><body><main><header><div class="brand">PLAYFORGE · {escape(__version__)}</div>
<h1>Run status</h1><p class="muted">Build a Coding Agent That Can Build a Game</p></header>
<div class="status" role="status">{escape(label)}</div><p class="warning">{escape(warning)}</p>
<div class="metrics"><div class="metric">API attempts<strong>{escape(str(usage.get('api_attempts','—')))}</strong></div>
<div class="metric">Elapsed seconds<strong>{escape(str(summary.get('duration_seconds','—')))}</strong></div>
<div class="metric">Selected round<strong>{escape(str(summary.get('selected_round','—')))}</strong></div></div>
<div class="actions">{links}</div><p class="muted">Run agent: {escape(str(summary.get('agent_version','not recorded')))} · Viewer: {escape(__version__)}</p><p>Selected checks are not complete gameplay acceptance. Failures and manual-review items remain visible.</p>
<section><h2>Requirements</h2><table><thead><tr><th>ID</th><th>Requirement</th><th>Result</th></tr></thead><tbody>{''.join(rows) or '<tr><td colspan="3">No requirement evidence yet.</td></tr>'}</tbody></table></section>
<section><h2>Recent activity</h2><ol>{timeline or '<li>No activity evidence yet.</li>'}</ol></section>
<footer>Read-only local viewer · refreshes every 5 seconds · no model calls, keys or raw API logs exposed</footer>
</main></body></html>'''


def make_dashboard_server(root, port=8005):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError("Dashboard needs an existing run directory")

    class Handler(GameHandler):
        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/":
                body = render_dashboard(root).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
            elif path == "/report":
                try:
                    body = read_text(root / "REPORT.md").encode("utf-8")
                except (OSError, ValueError):
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(body)
            elif path.startswith("/game/") and snapshot(root)["has_game"]:
                self.path = self.path[len("/game"):]
                self.directory = str(root / "game")
                super().do_GET()
            else:
                self.send_error(404)

    server = ThreadingHTTPServer(("127.0.0.1", port), lambda *args, **kwargs: Handler(*args, directory=str(root / "game"), **kwargs))
    server.daemon_threads = True
    return server
