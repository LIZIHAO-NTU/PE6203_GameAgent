"""Trusted loopback-only static server. Never executes generated host code."""
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from urllib.parse import unquote, urlsplit

CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data:; font-src 'self' data:; connect-src 'none'; "
       "object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'")


class GameHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def end_headers(self):
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def list_directory(self, path):
        self.send_error(403, "Directory listing disabled")
        return None

    def do_GET(self):
        if urlsplit(self.path).path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        root = Path(self.directory).resolve()
        raw = unquote(urlsplit(self.path).path)
        target = root / raw.lstrip("/")
        try:
            if "\\" in raw or "\x00" in raw or not target.resolve().is_relative_to(root):
                self.send_error(403)
                return
            current = target
            while current != root:
                if current.is_symlink():
                    self.send_error(403)
                    return
                current = current.parent
        except (OSError, ValueError):
            self.send_error(403)
            return
        super().do_GET()

    def do_HEAD(self):
        # Use the same path checks, without sending a response body.
        self.send_error(405, "Use GET")


def make_server(root: Path, port=0):
    server = ThreadingHTTPServer(("127.0.0.1", port), partial(GameHandler, directory=str(root.resolve())))
    server.daemon_threads = True
    return server


@contextmanager
def running_server(root: Path):
    server = make_server(root)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
