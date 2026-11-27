"""Read-only HTTP front for recall: GET /recall?project=NAME&q=TEXT&k=3 -> plain-text block.

Bind to loopback or a private interface only. There is no auth: anyone who can reach the port
can read the configured notes through the search.
"""
from __future__ import annotations

import urllib.parse
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .recall import BackendFactory, recall
from .config import Settings


def make_handler(settings: Settings, backend_factory: BackendFactory) -> type[BaseHTTPRequestHandler]:
    allowed = settings.serving()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: str = "") -> None:
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            url = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(url.query)
            project = (qs.get("project") or [""])[0]
            if url.path != "/recall" or project not in allowed:
                return self._send(404, "not found\n")
            try:
                k = max(1, min(10, int((qs.get("k") or ["3"])[0])))
            except ValueError:
                k = 3
            cfg = replace(settings, k=k)
            block = recall((qs.get("q") or [""])[0], [project], cfg, backend_factory, surface="server")
            self._send(200, block + "\n" if block else "")

        def log_message(self, *args: object) -> None:  # the JSONL log is the record
            pass

    return Handler


def serve(settings: Settings, backend_factory: BackendFactory) -> None:
    handler = make_handler(settings, backend_factory)
    with ThreadingHTTPServer((settings.serve_host, settings.serve_port), handler) as srv:
        print(f"memory-recall serve on {settings.serve_host}:{settings.serve_port} "
              f"projects={sorted(settings.serving())}", flush=True)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
