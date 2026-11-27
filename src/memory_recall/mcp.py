"""Minimal MCP client (streamable-http) for a warm Basic Memory `bm mcp` server."""
from __future__ import annotations

import itertools
import json
import time
import urllib.request
from typing import Any

PROTOCOL_VERSION = "2025-06-18"


class McpError(Exception):
    pass


class McpClient:
    """One client = one server session. `timeout` is the TOTAL budget across all calls."""

    def __init__(self, url: str, timeout: float):
        self.url, self.timeout = url, timeout
        self._sid: str | None = None
        self._t0: float | None = None
        self._ids = itertools.count(1)

    def _left(self) -> float:
        if self._t0 is None:
            self._t0 = time.monotonic()
        left = self.timeout - (time.monotonic() - self._t0)
        if left <= 0:
            raise TimeoutError("mcp budget spent")
        return left

    def _post(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self._sid:
            headers["Mcp-Session-Id"] = self._sid
        req = urllib.request.Request(self.url, json.dumps(payload).encode(), headers, method="POST")
        with urllib.request.urlopen(req, timeout=self._left()) as r:
            self._sid = r.headers.get("Mcp-Session-Id") or self._sid
            body = r.read().decode("utf-8", "replace")
            ctype = r.headers.get_content_type()
        if "id" not in payload:  # notification: the server answers 202 with no body
            return None
        msgs: list[Any] = []
        if ctype == "text/event-stream":
            for line in body.splitlines():
                if line.startswith("data:"):
                    try:
                        msgs.append(json.loads(line[5:].strip()))
                    except ValueError:
                        pass
        elif body.strip():
            msgs.append(json.loads(body))
        match = [m for m in msgs if isinstance(m, dict) and m.get("id") == payload["id"]]
        if not match:
            raise McpError(f"no response for request {payload['id']}")
        if "error" in match[-1]:
            raise McpError(str(match[-1]["error"]))
        return match[-1]

    def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        msg = self._post({"jsonrpc": "2.0", "id": next(self._ids), "method": method, "params": params})
        assert msg is not None
        return msg["result"]

    def _ensure_session(self) -> None:
        if self._sid:
            return
        self._rpc("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "memory-recall", "version": "1"},
        })
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def call(self, tool: str, args: dict[str, Any]) -> Any:
        self._ensure_session()
        res = self._rpc("tools/call", {"name": tool, "arguments": args})
        text = res["content"][0]["text"]
        if res.get("isError"):  # tool errors arrive as plain text, not as JSON-RPC errors
            raise McpError(text[:300])
        try:
            return json.loads(text)
        except ValueError:
            raise McpError(text[:300]) from None

    def close(self) -> None:
        """Best-effort session end. The server keeps sessions until DELETE."""
        if not self._sid:
            return
        try:
            req = urllib.request.Request(self.url, headers={"Mcp-Session-Id": self._sid}, method="DELETE")
            urllib.request.urlopen(req, timeout=0.2).close()
        except Exception:
            pass
        self._sid = None
