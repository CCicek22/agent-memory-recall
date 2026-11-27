from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))  # metrics / retrieval / run_eval are plain modules

from memory_recall.config import Settings  # noqa: E402
from memory_recall.recall import Hit  # noqa: E402


class FakeBackend:
    """Stands in for Basic Memory. Records calls; can raise or sleep."""

    def __init__(self, hits: dict[str, list[Hit]], *, raises: Exception | None = None, delay: float = 0.0):
        self.hits, self.raises, self.delay = hits, raises, delay
        self.calls: list[tuple[str, str, int]] = []
        self.closed = 0

    def search(self, project: str, query: str, k: int) -> list[Hit]:
        import time
        self.calls.append((project, query, k))
        if self.delay:
            time.sleep(self.delay)
        if self.raises:
            raise self.raises
        return list(self.hits.get(project, []))

    def close(self) -> None:
        self.closed += 1


@pytest.fixture
def notes_dir(tmp_path: Path) -> Path:
    d = tmp_path / "notes"
    d.mkdir()
    return d


@pytest.fixture
def settings(tmp_path: Path, notes_dir: Path) -> Settings:
    return Settings(
        projects={"notes": str(notes_dir)},
        timeout=1.0,
        k=3,
        min_score=0.77,
        max_chars=600,
        model_tag="test-model",
        log_path=tmp_path / "state" / "recall.jsonl",
        off_file=tmp_path / "state" / "off",
    )


def write_note(d: Path, stem: str, body: str = "Body text.", *, title: str | None = None,
               description: str | None = None) -> str:
    fm = ["---", f"title: {title or stem}"]
    if description:
        fm.append(f"description: {description}")
    fm.append("---")
    (d / f"{stem}.md").write_text("\n".join(fm) + f"\n\n# {title or stem}\n\n{body}\n", encoding="utf-8")
    return f"{stem}.md"
