"""Search backends. The default talks to a warm Basic Memory MCP server."""
from __future__ import annotations

from .mcp import McpClient
from .recall import Hit


class BasicMemoryBackend:
    """search_notes over MCP. Vector search only: Basic Memory's hybrid mode fuses full-text
    scores that land near 1.0 and swamp the vector scores, so keyword order wins (measured,
    see eval/RESULTS.md)."""

    def __init__(self, url: str, timeout: float):
        self._client = McpClient(url, timeout)

    def search(self, project: str, query: str, k: int) -> list[Hit]:
        out = self._client.call("search_notes", {
            "query": query,
            "project": project,
            "page_size": k,
            "search_type": "vector",
            "output_format": "json",
        })
        return [
            Hit(project=project, file_path=r.get("file_path") or "", title=r.get("title") or "",
                score=float(r.get("score") or 0.0))
            for r in out.get("results", [])
        ]

    def close(self) -> None:
        self._client.close()
