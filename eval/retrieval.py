"""Reference retrievers for the demo eval: cosine over embeddings, BM25, and a reciprocal-rank fusion.

Stdlib only. Not Basic Memory: the eval runs without its index, so the numbers measure these
three ranking methods, not bm's hybrid mode.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence

STOPWORDS = frozenset(
    "a an and are as at be by do does for from how i if in into is it its of on or should so that the "
    "this to was what when which with you your my can".split()
)
_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS]


def rank_by_scores(scores: Mapping[str, float]) -> list[str]:
    """Doc ids sorted by score, highest first; ties broken by id so results are deterministic."""
    return [doc for doc, _ in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))]


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def vector_scores(query_vec: Sequence[float], doc_vecs: Mapping[str, Sequence[float]]) -> dict[str, float]:
    return {doc: cosine(query_vec, vec) for doc, vec in doc_vecs.items()}


def bm25_scores(query: str, docs: Mapping[str, str], k1: float = 1.5, b: float = 0.75) -> dict[str, float]:
    """Okapi BM25 over the tokenized docs. Docs with no matching term score 0."""
    toks = {doc: tokenize(text) for doc, text in docs.items()}
    n = len(toks)
    avgdl = (sum(len(t) for t in toks.values()) / n) if n else 0.0
    df: Counter[str] = Counter()
    for t in toks.values():
        df.update(set(t))
    q_terms = set(tokenize(query))
    out: dict[str, float] = {}
    for doc, t in toks.items():
        tf = Counter(t)
        dl = len(t) or 1
        score = 0.0
        for term in q_terms:
            if tf[term] == 0:
                continue
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            score += idf * tf[term] * (k1 + 1) / (tf[term] + k1 * (1 - b + b * dl / avgdl))
        out[doc] = score
    return out


def rrf_fuse(rankings: Sequence[Sequence[str]], k: int = 60) -> dict[str, float]:
    """Reciprocal-rank fusion: sum of 1/(k + rank) over the input rankings."""
    fused: dict[str, float] = {}
    for ranking in rankings:
        for pos, doc in enumerate(ranking, 1):
            fused[doc] = fused.get(doc, 0.0) + 1.0 / (k + pos)
    return fused
