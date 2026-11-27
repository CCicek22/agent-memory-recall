"""Ranking metrics. A ranking is a list of doc ids, best first. `expect` is one doc id."""
from __future__ import annotations

from collections.abc import Sequence


def rank_of(expect: str, ranking: Sequence[str]) -> int | None:
    """1-based position of `expect`, or None when absent."""
    try:
        return ranking.index(expect) + 1
    except ValueError:
        return None


def hit_at(ranks: Sequence[int | None], k: int) -> float:
    """Fraction of queries whose expected doc is in the top k."""
    if not ranks:
        return 0.0
    return sum(1 for r in ranks if r is not None and r <= k) / len(ranks)


def mrr_at(ranks: Sequence[int | None], k: int = 10) -> float:
    """Mean reciprocal rank, zero for a miss beyond rank k."""
    if not ranks:
        return 0.0
    return sum(1 / r for r in ranks if r is not None and r <= k) / len(ranks)
