from __future__ import annotations

import json
from pathlib import Path

import pytest

from memory_recall.config import Settings, parse_projects
from memory_recall.hook import hook_query, run_hook
from memory_recall.recall import Hit
from conftest import FakeBackend, write_note


@pytest.mark.parametrize("prompt", ["", "short one", "/compact the context now", "<task-notification>done</task-notification>"])
def test_hook_query_ignores_non_prompts(prompt: str) -> None:
    assert hook_query({"prompt": prompt}) is None


def test_hook_query_accepts_real_prompt() -> None:
    assert hook_query({"prompt": "  how do I rotate a leaked token?  "}) == "how do I rotate a leaked token?"
    assert hook_query("not a dict") is None


def test_run_hook_emits_hook_json(settings, notes_dir: Path) -> None:
    f = write_note(notes_dir, "lesson")
    be = FakeBackend({"notes": [Hit("notes", f, title="lesson", score=0.9)]})
    out = run_hook(json.dumps({"prompt": "how do I rotate a leaked token"}), settings, lambda: be)
    payload = json.loads(out)["hookSpecificOutput"]
    assert payload["hookEventName"] == "UserPromptSubmit"
    assert "1. lesson" in payload["additionalContext"]


def test_run_hook_fails_open_on_bad_json(settings, capsys) -> None:
    be = FakeBackend({})
    assert run_hook("{not json", settings, lambda: be) == ""
    assert "JSONDecodeError" in capsys.readouterr().err
    assert be.calls == []


def test_run_hook_without_projects_is_silent(settings) -> None:
    from dataclasses import replace
    be = FakeBackend({})
    assert run_hook(json.dumps({"prompt": "a long enough prompt"}), replace(settings, projects={}), lambda: be) == ""


def test_parse_projects() -> None:
    assert parse_projects("a=/x, b=~/y ,") == {"a": "/x", "b": "~/y"}
    assert parse_projects("") == {}
    with pytest.raises(ValueError):
        parse_projects("no-equals-sign")


def test_from_env_reads_overrides(tmp_path: Path) -> None:
    env = {
        "MEMORY_RECALL_PROJECTS": "notes=/n,runbooks=/r",
        "MEMORY_RECALL_SERVE_PROJECTS": "runbooks",
        "MEMORY_RECALL_MIN_SCORE": "0.8",
        "MEMORY_RECALL_TIMEOUT": "2.5",
        "MEMORY_RECALL_MAX_CHARS": "400",
        "MEMORY_RECALL_LOG": str(tmp_path / "l.jsonl"),
    }
    s = Settings.from_env(env)
    assert s.projects == {"notes": "/n", "runbooks": "/r"}
    assert s.serving() == {"runbooks"}
    assert (s.min_score, s.timeout, s.max_chars) == (0.8, 2.5, 400)
    assert s.log_path == tmp_path / "l.jsonl"


def test_serving_defaults_to_all_projects() -> None:
    assert Settings(projects={"a": "/a", "b": "/b"}).serving() == {"a", "b"}
