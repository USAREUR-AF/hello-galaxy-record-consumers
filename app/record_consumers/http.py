"""A small HTTP server on the standard library, shared by the two services."""
from __future__ import annotations

import json
import os
import signal
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_BODY_BYTES = 1024 * 1024  # a first-bite record carries the frame twice in base64; 1 MiB is ample


class Handler(BaseHTTPRequestHandler):
    server_version = "record-consumers"
    sys_version = ""
    protocol_version = "HTTP/1.1"
    routes: dict = {}  # (method, path) -> function(handler) -> (status, content type, body)

    def _dispatch(self, method: str) -> None:
        path = self.path.split("?", 1)[0]
        route = self.routes.get((method, path))
        if route is None:
            known = any(known_path == path for _, known_path in self.routes)
            status, kind, body = (405, "text/plain", "method not allowed\n") if known else (404, "text/plain", "not found\n")
        else:
            try:
                status, kind, body = route(self)
            except Exception as error:  # a fault in one request must not end the server
                print(f"error: {method} {path}: {error!r}", file=sys.stderr, flush=True)
                status, kind, body = 500, "text/plain", "internal error\n"
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", f"{kind}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        if kind == "text/html":
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802 (the base class's naming)
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch("POST")

    def body(self) -> bytes | None:
        """The request body, or None when it is absent or over the limit."""
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return None
        if length < 0 or length > MAX_BODY_BYTES:
            self.close_connection = True
            return None
        return self.rfile.read(length)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        if not self.path.startswith(("/healthz", "/readyz")):
            print(f"{self.command} {self.path.split('?', 1)[0]} {args[1] if len(args) > 1 else ''}", flush=True)


def reply_json(status: int, value) -> tuple:
    return status, "application/json", json.dumps(value, separators=(",", ":")) + "\n"


def serve(routes: dict, name: str) -> None:
    """Serve until SIGTERM or SIGINT. Listens on LISTEN_ADDRESS:LISTEN_PORT."""
    handler = type("Routes", (Handler,), {"routes": routes})
    address = (os.environ.get("LISTEN_ADDRESS", "0.0.0.0"), int(os.environ.get("LISTEN_PORT", "8080")))
    server = ThreadingHTTPServer(address, handler)
    server.daemon_threads = True
    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, lambda *_: threading.Thread(target=server.shutdown, daemon=True).start())
    print(f"{name}: listening on {address[0]}:{address[1]}", flush=True)
    server.serve_forever()
    print(f"{name}: stopped", flush=True)
