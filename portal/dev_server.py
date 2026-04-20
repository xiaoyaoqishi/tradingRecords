#!/usr/bin/env python3
"""Local portal dev server.

Serves static files under ./portal and proxies app paths:
- /api/      -> backend (default 127.0.0.1:8000)
- /trading/  -> frontend vite (default 127.0.0.1:5173)
- /notes/    -> notes vite (default 127.0.0.1:5174)
- /monitor/  -> monitor vite (default 127.0.0.1:5175)
- /ledger/   -> ledger vite (default 127.0.0.1:5176)
"""

from __future__ import annotations

import http.client
import os
import socket
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


ROOT_DIR = Path(__file__).resolve().parent


def _env_port(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default)).strip()
    try:
        port = int(raw)
    except ValueError as exc:
        raise SystemExit(f"{name} must be an integer, got: {raw!r}") from exc
    if not (1 <= port <= 65535):
        raise SystemExit(f"{name} out of range: {port}")
    return port


PORTAL_DEV_PORT = _env_port("PORTAL_DEV_PORT", 5172)
UPSTREAMS = {
    "/api/": ("localhost", _env_port("PORTAL_BACKEND_PORT", 8000)),
    "/trading/": ("localhost", _env_port("PORTAL_TRADING_PORT", 5173)),
    "/notes/": ("localhost", _env_port("PORTAL_NOTES_PORT", 5174)),
    "/monitor/": ("localhost", _env_port("PORTAL_MONITOR_PORT", 5175)),
    "/ledger/": ("localhost", _env_port("PORTAL_LEDGER_PORT", 5176)),
}

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


class PortalDevHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT_DIR), **kwargs)

    def do_GET(self):
        self._dispatch()

    def do_HEAD(self):
        self._dispatch()

    def do_POST(self):
        self._dispatch()

    def do_PUT(self):
        self._dispatch()

    def do_PATCH(self):
        self._dispatch()

    def do_DELETE(self):
        self._dispatch()

    def do_OPTIONS(self):
        self._dispatch()

    def list_directory(self, path):
        self.send_error(403, "Directory listing is disabled")
        return None

    def _dispatch(self):
        upstream = self._match_upstream(self.path)
        if upstream:
            self._proxy_to(upstream)
            return

        if self.command not in {"GET", "HEAD"}:
            self.send_error(405, "Method Not Allowed")
            return

        self.path = self._rewrite_static_path(self.path)
        if self.command == "GET":
            super().do_GET()
        else:
            super().do_HEAD()

    @staticmethod
    def _match_upstream(raw_path: str):
        parsed = urlsplit(raw_path)
        for prefix, upstream in UPSTREAMS.items():
            if parsed.path.startswith(prefix):
                return upstream
        return None

    @staticmethod
    def _rewrite_static_path(raw_path: str) -> str:
        parsed = urlsplit(raw_path)
        path = parsed.path
        if path == "/":
            path = "/index.html"
        elif path == "/login":
            path = "/login.html"
        if parsed.query:
            return f"{path}?{parsed.query}"
        return path

    def _proxy_to(self, upstream: tuple[str, int]):
        host, port = upstream
        parsed = urlsplit(self.path)
        upstream_path = parsed.path
        if parsed.query:
            upstream_path = f"{upstream_path}?{parsed.query}"

        body = None
        content_len = self.headers.get("Content-Length")
        if content_len:
            try:
                read_len = int(content_len)
            except ValueError:
                self.send_error(400, "Invalid Content-Length")
                return
            body = self.rfile.read(read_len) if read_len > 0 else b""

        req_headers: dict[str, str] = {}
        for key, value in self.headers.items():
            k = key.lower()
            if k == "host" or k in HOP_BY_HOP_HEADERS:
                continue
            req_headers[key] = value

        req_headers["Host"] = f"{host}:{port}"
        req_headers["X-Forwarded-For"] = self.client_address[0]
        req_headers["X-Forwarded-Host"] = self.headers.get("Host", "")
        req_headers["X-Forwarded-Proto"] = "http"

        conn = http.client.HTTPConnection(host, port, timeout=60)
        try:
            conn.request(self.command, upstream_path, body=body, headers=req_headers)
            upstream_resp = conn.getresponse()
            payload = upstream_resp.read()
        except (ConnectionRefusedError, socket.timeout, OSError) as exc:
            self.send_error(502, f"Upstream unavailable: {host}:{port} ({exc})")
            return
        finally:
            conn.close()

        self.send_response(upstream_resp.status, upstream_resp.reason)
        for key, value in upstream_resp.getheaders():
            k = key.lower()
            if k in HOP_BY_HOP_HEADERS or k == "content-length":
                continue
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()

        if self.command != "HEAD":
            self.wfile.write(payload)


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORTAL_DEV_PORT), PortalDevHandler)
    print(
        f"[portal-dev] listening on http://127.0.0.1:{PORTAL_DEV_PORT} "
        f"(api={UPSTREAMS['/api/'][1]}, trading={UPSTREAMS['/trading/'][1]}, "
        f"notes={UPSTREAMS['/notes/'][1]}, monitor={UPSTREAMS['/monitor/'][1]}, "
        f"ledger={UPSTREAMS['/ledger/'][1]})"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
