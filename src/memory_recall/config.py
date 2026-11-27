"""Settings from environment variables. Every knob has a default; nothing is read from a home path."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

DEFAULT_MIN_SCORE = 0.77  # calibrated for embeddinggemma-256 vector scores; recalibrate per model
DEFAULT_TIMEOUT = 1.8  # total budget for one recall, seconds
DEFAULT_MAX_CHARS = 600
DEFAULT_MCP_URL = "http://127.0.0.1:8791/mcp"
DEFAULT_SERVE_HOST = "127.0.0.1"
DEFAULT_SERVE_PORT = 8792
DEFAULT_SKIP_FILES = ("MEMORY.md", "index-*.md")


def _state_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return Path(base) / "memory-recall"


def parse_projects(raw: str) -> dict[str, str]:
    """'notes=~/notes,runbooks=/srv/runbooks' -> {'notes': '~/notes', 'runbooks': '/srv/runbooks'}."""
    out: dict[str, str] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        name, sep, path = part.partition("=")
        if not sep or not name.strip() or not path.strip():
            raise ValueError(f"bad project entry {part!r}; expected name=/path")
        out[name.strip()] = path.strip()
    return out


@dataclass(frozen=True)
class Settings:
    mcp_url: str = DEFAULT_MCP_URL
    projects: dict[str, str] = field(default_factory=dict)  # name -> notes dir (for frontmatter lookup)
    serve_projects: frozenset[str] | None = None  # None = all configured projects
    serve_host: str = DEFAULT_SERVE_HOST
    serve_port: int = DEFAULT_SERVE_PORT
    timeout: float = DEFAULT_TIMEOUT
    k: int = 3
    min_score: float = DEFAULT_MIN_SCORE
    max_chars: int = DEFAULT_MAX_CHARS
    model_tag: str = "vector"
    skip_files: tuple[str, ...] = DEFAULT_SKIP_FILES
    log_path: Path = field(default_factory=lambda: _state_dir() / "recall.jsonl")
    off_file: Path = field(default_factory=lambda: _state_dir() / "off")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if environ is None else environ
        serve = env.get("MEMORY_RECALL_SERVE_PROJECTS", "").strip()
        return cls(
            mcp_url=env.get("MEMORY_RECALL_MCP_URL", DEFAULT_MCP_URL),
            projects=parse_projects(env.get("MEMORY_RECALL_PROJECTS", "")),
            serve_projects=frozenset(p.strip() for p in serve.split(",") if p.strip()) or None,
            serve_host=env.get("MEMORY_RECALL_SERVE_HOST", DEFAULT_SERVE_HOST),
            serve_port=int(env.get("MEMORY_RECALL_SERVE_PORT", DEFAULT_SERVE_PORT)),
            timeout=float(env.get("MEMORY_RECALL_TIMEOUT", DEFAULT_TIMEOUT)),
            min_score=float(env.get("MEMORY_RECALL_MIN_SCORE", DEFAULT_MIN_SCORE)),
            max_chars=int(env.get("MEMORY_RECALL_MAX_CHARS", DEFAULT_MAX_CHARS)),
            model_tag=env.get("MEMORY_RECALL_MODEL_TAG", "vector"),
            skip_files=tuple(p.strip() for p in env.get("MEMORY_RECALL_SKIP_FILES", ",".join(DEFAULT_SKIP_FILES)).split(",") if p.strip()),
            log_path=Path(env.get("MEMORY_RECALL_LOG", str(_state_dir() / "recall.jsonl"))).expanduser(),
            off_file=Path(env.get("MEMORY_RECALL_OFF_FILE", str(_state_dir() / "off"))).expanduser(),
        )

    def serving(self) -> set[str]:
        """Projects the HTTP server may answer for."""
        return set(self.projects) if self.serve_projects is None else set(self.serve_projects)

    def is_off(self, environ: Mapping[str, str] | None = None) -> bool:
        env = os.environ if environ is None else environ
        return env.get("MEMORY_RECALL_OFF") == "1" or self.off_file.exists()
