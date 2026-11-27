from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path

import pytest

from memory_recall.config import Settings
from memory_recall.recall import Hit, format_block, note_meta, recall
from conftest import FakeBackend, write_note


def factory_for(backend: FakeBackend):
    return lambda: backend


def hit(project: str, file_path: str, score: float, title: str = "") -> Hit:
    stem = Path(file_path).stem
    return Hit(project=project, file_path=file_path, title=title or stem, score=score)


def test_block_lists_hits_best_first_with_description(settings: Settings, notes_dir: Path) -> None:
    a = write_note(notes_dir, "lesson-a", description="Explains retries")
    b = write_note(notes_dir, "lesson-b")
    be = FakeBackend({"notes": [hit("notes", b, 0.80), hit("notes", a, 0.90)]})
    out = recall("retry policy question", ["notes"], settings, factory_for(be))
    lines = out.splitlines()
    assert lines[0].startswith("[memory recall · notes · 2 hits · test-model")
    assert lines[1] == "1. lesson-a — Explains retries"
    assert lines[2] == "2. lesson-b"
    assert lines[-1].startswith("Open the note")
    assert be.closed == 1


def test_fail_open_on_backend_error(settings: Settings) -> None:
    be = FakeBackend({}, raises=ConnectionError("server down"))
    assert recall("anything at all", ["notes"], settings, factory_for(be)) == ""
    row = json.loads(settings.log_path.read_text().splitlines()[-1])
    assert row["error"].startswith("ConnectionError: server down")


def test_timeout_returns_empty_within_budget(settings: Settings) -> None:
    slow = FakeBackend({"notes": [hit("notes", "x.md", 0.99)]}, delay=0.5)
    cfg = replace(settings, timeout=0.1)
    t0 = time.monotonic()
    assert recall("slow backend query", ["notes"], cfg, factory_for(slow)) == ""
    assert time.monotonic() - t0 < 0.4
    row = json.loads(settings.log_path.read_text().splitlines()[-1])
    assert row["error"].startswith("timeout after")


def test_min_score_cut_is_inclusive(settings: Settings, notes_dir: Path) -> None:
    keep = write_note(notes_dir, "keep")
    drop = write_note(notes_dir, "drop")
    be = FakeBackend({"notes": [hit("notes", keep, 0.77), hit("notes", drop, 0.7699)]})
    out = recall("cutoff check question", ["notes"], settings, factory_for(be))
    assert "1. keep" in out and "drop" not in out


def test_max_chars_cut_truncates_with_ellipsis(settings: Settings, notes_dir: Path) -> None:
    files = [write_note(notes_dir, f"n{i}", description="long " * 40) for i in range(3)]
    be = FakeBackend({"notes": [hit("notes", f, 0.9 - i * 0.01) for i, f in enumerate(files)]})
    out = recall("long descriptions question", ["notes"], replace(settings, max_chars=160), factory_for(be))
    assert len(out) <= 160
    assert out.endswith("…")


def test_footer_dropped_when_space_is_short() -> None:
    from memory_recall.recall import Note
    out = format_block(["notes"], [("a", Note(None, ""), "a")], "m", max_chars=110)
    assert "Open the note" not in out
    assert len(out) <= 110


def test_superseded_note_is_skipped_and_next_hit_fills_slot(settings: Settings, notes_dir: Path) -> None:
    old = notes_dir / "old.md"
    old.write_text("---\ntitle: old\n---\n\n**SUPERSEDED (2026-01-02):** use the new rule\n", encoding="utf-8")
    fresh = write_note(notes_dir, "fresh")
    be = FakeBackend({"notes": [hit("notes", "old.md", 0.95), hit("notes", fresh, 0.90)]})
    out = recall("superseded slot question", ["notes"], replace(settings, k=1), factory_for(be))
    assert "1. fresh" in out and "old" not in out


def test_update_marker_points_reader_to_note(settings: Settings, notes_dir: Path) -> None:
    (notes_dir / "upd.md").write_text("---\ntitle: upd\n---\n\n**UPDATE:** the number changed\n", encoding="utf-8")
    be = FakeBackend({"notes": [hit("notes", "upd.md", 0.9)]})
    out = recall("update marker question", ["notes"], settings, factory_for(be))
    assert "1. upd [UPDATE: open it]" in out


def test_index_files_are_skipped(settings: Settings, notes_dir: Path) -> None:
    write_note(notes_dir, "MEMORY", "index")
    write_note(notes_dir, "index-topic")
    be = FakeBackend({"notes": [hit("notes", "MEMORY.md", 0.95), hit("notes", "index-topic.md", 0.94)]})
    assert recall("index files question", ["notes"], settings, factory_for(be)) == ""


def test_kill_switch_env_skips_backend_and_logs(settings: Settings) -> None:
    be = FakeBackend({"notes": [hit("notes", "x.md", 0.99)]})
    out = recall("kill switch env question", ["notes"], settings, factory_for(be),
                 environ={"MEMORY_RECALL_OFF": "1"})
    assert out == "" and be.calls == []
    assert json.loads(settings.log_path.read_text().splitlines()[-1])["skipped"] == "off"


def test_kill_switch_file_skips_backend(settings: Settings) -> None:
    settings.off_file.parent.mkdir(parents=True, exist_ok=True)
    settings.off_file.touch()
    be = FakeBackend({"notes": [hit("notes", "x.md", 0.99)]})
    assert recall("kill switch file question", ["notes"], settings, factory_for(be), environ={}) == ""
    assert be.calls == []


def test_jsonl_row_per_call(settings: Settings, notes_dir: Path) -> None:
    f = write_note(notes_dir, "logged")
    be = FakeBackend({"notes": [hit("notes", f, 0.91)]})
    recall("logging question here", ["notes"], settings, factory_for(be), surface="hook")
    recall("", ["notes"], settings, factory_for(be))  # empty query: no row, no call
    rows = [json.loads(line) for line in settings.log_path.read_text().splitlines()]
    assert len(rows) == 1
    assert set(rows[0]) >= {"ts", "surface", "projects", "q", "hits", "ms"}
    assert rows[0]["surface"] == "hook"
    assert rows[0]["hits"] == [[f, 0.91]]


def test_search_asks_for_double_k(settings: Settings) -> None:
    be = FakeBackend({"notes": []})
    recall("k doubling question", ["notes"], settings, factory_for(be))
    assert be.calls == [("notes", "k doubling question", 6)]


def test_note_meta_reads_description_and_marker(notes_dir: Path, settings: Settings) -> None:
    write_note(notes_dir, "d", description="'quoted: desc'")
    m = note_meta(settings, "notes", "d.md")
    assert m.description == "quoted: desc" and m.marker == ""
    assert note_meta(settings, "notes", "missing.md").description is None
    assert note_meta(settings, "nope", "d.md").marker == ""
