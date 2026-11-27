"""Claude Code UserPromptSubmit hook adapter: event JSON on stdin, hook JSON on stdout."""
from __future__ import annotations

import json
import sys
from typing import Any, Mapping

from .backends import BasicMemoryBackend
from .config import Settings
from .recall import BackendFactory, recall

MIN_PROMPT_CHARS = 15


def hook_query(event: Any) -> str | None:
    """The prompt to search for, or None when the event is not a real user prompt."""
    prompt = (event.get("prompt") or "").strip() if isinstance(event, dict) else ""
    if prompt.startswith("<task-notification>"):  # background-task event, not a task
        return None
    if len(prompt) < MIN_PROMPT_CHARS or prompt.startswith("/"):  # short prompts and slash commands
        return None
    return prompt


def hook_output(block: str) -> str:
    return json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": block}})


def run_hook(stdin_text: str, settings: Settings, backend_factory: BackendFactory,
             environ: Mapping[str, str] | None = None) -> str:
    """Return the hook JSON to print, or "" for no output. Never raises."""
    try:
        query = hook_query(json.loads(stdin_text or "{}"))
        if not query or not settings.projects:
            return ""
        block = recall(query, list(settings.projects), settings, backend_factory,
                       surface="hook", environ=environ)
        return hook_output(block) if block else ""
    except Exception as e:  # a hook must never fail the prompt
        print(f"memory-recall: {type(e).__name__}: {e}", file=sys.stderr)
        return ""


def default_backend_factory(settings: Settings) -> BackendFactory:
    return lambda: BasicMemoryBackend(settings.mcp_url, settings.timeout)


def hook_main(settings: Settings) -> int:
    out = run_hook(sys.stdin.read(), settings, default_backend_factory(settings))
    if out:
        print(out)
    return 0
