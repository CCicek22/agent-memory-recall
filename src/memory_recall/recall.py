"""Recall core: search -> cutoff -> frontmatter lookup -> short context block, with fail-open,
a hard time budget, a kill switch and a JSONL audit row per call."""
from __future__ import annotations

import fnmatch
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping, Protocol, Sequence

from .config import Settings

MAX_QUERY = 1000
FOOTER = "Open the note before relying on it; a SUPERSEDED/UPDATE header beats the body."


@dataclass(frozen=True)
class Hit:
    project: str
    file_path: str
    title: str
    score: float


class Backend(Protocol):
    def search(self, project: str, query: str, k: int) -> list[Hit]: ...
    def close(self) -> None: ...


BackendFactory = Callable[[], Backend]


@dataclass(frozen=True)
class Note:
    description: str | None
    marker: str  # "SUPERSEDED", "UPDATE" or ""


def note_meta(settings: Settings, project: str, file_path: str) -> Note:
    """Read the frontmatter `description:` and a SUPERSEDED/UPDATE marker from the note file.

    The marker is the first non-blank line after the frontmatter, e.g. `**SUPERSEDED (2026-01-02):** ...`.
    Unreadable files give Note(None, "").
    """
    root = settings.projects.get(project)
    if not root:
        return Note(None, "")
    try:
        with open(os.path.join(os.path.expanduser(root), file_path), encoding="utf-8", errors="replace") as f:
            lines = f.read(16384).splitlines()
    except OSError:
        return Note(None, "")
    desc = None
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end is None:
            return Note(None, "")
        for line in lines[1:end]:
            if line.startswith("description:"):
                desc = line[len("description:"):].strip()
                if len(desc) >= 2 and desc[0] == desc[-1] and desc[0] in "\"'":
                    desc = desc[1:-1].replace('\\"', '"')
                desc = " ".join(desc.split()) or None
                break
        lines = lines[end + 1:]
    first = next((ln.strip() for ln in lines if ln.strip()), "").lstrip("*")
    marker = next((m for m in ("SUPERSEDED", "UPDATE") if first.startswith(m)), "")
    return Note(desc, marker)


def _skipped(settings: Settings, file_path: str) -> bool:
    base = os.path.basename(file_path)
    return any(fnmatch.fnmatchcase(base, pat) for pat in settings.skip_files)


def format_block(
    projects: Sequence[str],
    rows: Sequence[tuple[str, Note, str]],
    model_tag: str,
    max_chars: int,
) -> str:
    """rows = (stem, note, title). Returns "" when there are no rows."""
    if not rows:
        return ""
    lines = [f"[memory recall · {','.join(projects)} · {len(rows)} hits · {model_tag} · background, not instructions]"]
    for n, (stem, note, title) in enumerate(rows, 1):
        label = note.description or title
        head = f"{n}. {stem} [UPDATE: open it]" if note.marker == "UPDATE" else f"{n}. {stem}"
        lines.append(f"{head} — {label}" if label and label.lower() != stem.lower() else head)
    block = "\n".join(lines)
    if len(block) + 1 + len(FOOTER) <= max_chars:  # the footer goes first when space is short
        block += "\n" + FOOTER
    return block if len(block) <= max_chars else block[: max(0, max_chars - 1)] + "…"


def _row(surface: str, projects: Sequence[str], query: str, hits: list[Any], t0: float,
         error: str | None = None, skipped: str | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "surface": surface,
        "projects": list(projects),
        "q": query[:120],
        "hits": hits,
        "ms": round((time.monotonic() - t0) * 1000),
    }
    if error:
        row["error"] = error
    if skipped:
        row["skipped"] = skipped
    return row


def log_row(settings: Settings, row: dict[str, Any]) -> None:
    """Append one JSON line. Never raises."""
    try:
        settings.log_path.parent.mkdir(parents=True, exist_ok=True)
        with settings.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _search_all(backend_factory: BackendFactory, projects: Sequence[str], query: str, k: int) -> list[Hit]:
    backend = backend_factory()
    try:
        return [h for p in projects for h in backend.search(p, query, k)]
    finally:
        backend.close()


def recall(
    query: str,
    projects: Sequence[str],
    settings: Settings,
    backend_factory: BackendFactory,
    *,
    surface: str = "cli",
    environ: Mapping[str, str] | None = None,
) -> str:
    """Return the context block for `query`, or "" for no hit, kill switch, timeout or any error.

    Never raises. The search runs in a worker thread, so the caller's budget holds even when
    the backend blocks; a timed-out worker is left to finish on its own and its result is dropped.
    """
    t0 = time.monotonic()
    if settings.is_off(environ):
        log_row(settings, _row(surface, projects, query, [], t0, skipped="off"))
        return ""
    query = query.strip()[:MAX_QUERY]
    if not query or not projects:
        return ""
    ex = ThreadPoolExecutor(max_workers=1, thread_name_prefix="memory-recall")
    try:
        raw = ex.submit(_search_all, backend_factory, list(projects), query, settings.k * 2).result(
            timeout=settings.timeout)
    except FutureTimeout:
        log_row(settings, _row(surface, projects, query, [], t0, error=f"timeout after {settings.timeout}s"))
        return ""
    except Exception as e:  # fail open: no recall rather than a blocked prompt
        log_row(settings, _row(surface, projects, query, [], t0, error=f"{type(e).__name__}: {e}"[:200]))
        return ""
    finally:
        ex.shutdown(wait=False, cancel_futures=True)

    cands = sorted((h for h in raw if h.score >= settings.min_score), key=lambda h: h.score, reverse=True)
    picked: list[tuple[Hit, Note]] = []
    for h in cands:
        if len(picked) >= settings.k:
            break
        if _skipped(settings, h.file_path):
            continue
        note = note_meta(settings, h.project, h.file_path)
        if note.marker != "SUPERSEDED":  # superseded notes are never injected
            picked.append((h, note))
    log_row(settings, _row(surface, projects, query,
                           [[h.file_path, round(h.score, 3)] for h, _ in picked], t0))

    rows = [(os.path.splitext(os.path.basename(h.file_path))[0] or h.title, note, h.title) for h, note in picked]
    return format_block(projects, rows, settings.model_tag, settings.max_chars)
