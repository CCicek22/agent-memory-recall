#!/usr/bin/env python3
"""Score vector, keyword (BM25) and fused retrieval on a corpus of Markdown notes.

  python eval/run_eval.py [--corpus eval/corpus] [--queries eval/queries.jsonl]
                          [--embed-url http://127.0.0.1:8790/v1/embeddings] [--dims 256]
                          [--json OUT] [--verbose]

Each query line: {"q": str, "kind": "nl" | "kw", "expect": "<note file stem>"}.
Vector mode needs a running embedding server (embed/embed_server.py). BM25 needs nothing.
Reports hit@3 and MRR@10 per mode, overall and per query kind.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from metrics import hit_at, mrr_at, rank_of  # noqa: E402
from retrieval import bm25_scores, rank_by_scores, rrf_fuse, vector_scores  # noqa: E402

MODES = ("vector", "keyword", "fused")
BATCH = 16


def load_corpus(corpus: Path) -> dict[str, str]:
    docs = {p.stem: p.read_text(encoding="utf-8") for p in sorted(corpus.glob("*.md"))}
    if not docs:
        raise SystemExit(f"no .md notes in {corpus}")
    return docs


def load_queries(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for r in rows:
        if {"q", "kind", "expect"} - r.keys():
            raise SystemExit(f"bad query row: {r}")
    return rows


def embed(url: str, texts: list[str], dims: int) -> list[list[float]]:
    """POST to an OpenAI-style /v1/embeddings endpoint, in batches. Returns vectors in input order."""
    out: list[list[float]] = []
    for i in range(0, len(texts), BATCH):
        body = json.dumps({"input": texts[i:i + BATCH], "dimensions": dims}).encode()
        req = urllib.request.Request(url, body, {"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())["data"]
        out.extend(d["embedding"] for d in sorted(data, key=lambda d: d["index"]))
    return out


def run(docs: dict[str, str], queries: list[dict[str, Any]], embed_url: str | None, dims: int) -> dict[str, Any]:
    """Per query: rankings per mode, the expected doc's rank, and cosine stats for calibration."""
    doc_ids = list(docs)
    vec_docs: dict[str, list[float]] = {}
    q_vecs: list[list[float]] = []
    if embed_url:
        doc_vecs = embed(embed_url, [docs[d] for d in doc_ids], dims)
        vec_docs = dict(zip(doc_ids, doc_vecs))
        q_vecs = embed(embed_url, [r["q"] for r in queries], dims)
    rows = []
    for i, r in enumerate(queries):
        kw = bm25_scores(r["q"], docs)
        kw_rank = rank_by_scores(kw)
        rankings = {"keyword": kw_rank}
        vec_s: dict[str, float] = {}
        if embed_url:
            vec_s = vector_scores(q_vecs[i], vec_docs)
            vec_rank = rank_by_scores(vec_s)
            rankings["vector"] = vec_rank
            rankings["fused"] = rank_by_scores(rrf_fuse([vec_rank, kw_rank]))
        ranks = {m: rank_of(r["expect"], rankings[m]) for m in rankings}
        other = [s for d, s in vec_s.items() if d != r["expect"]]
        rows.append({
            "q": r["q"], "kind": r["kind"], "expect": r["expect"], "ranks": ranks,
            "expect_cos": round(vec_s.get(r["expect"], 0.0), 3) if vec_s else None,
            "best_other_cos": round(max(other), 3) if other else None,
        })
    return {"n_docs": len(docs), "n_queries": len(queries), "rows": rows}


def summarize(rows: list[dict[str, Any]], mode: str, kind: str | None = None) -> dict[str, float] | None:
    sel = [r for r in rows if (kind is None or r["kind"] == kind) and mode in r["ranks"]]
    if not sel:
        return None
    ranks = [r["ranks"][mode] for r in sel]
    return {"n": len(sel), "hit@3": round(hit_at(ranks, 3), 3), "mrr@10": round(mrr_at(ranks, 10), 3)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", type=Path, default=HERE / "corpus")
    ap.add_argument("--queries", type=Path, default=HERE / "queries.jsonl")
    ap.add_argument("--embed-url", default=None, help="enables vector and fused modes")
    ap.add_argument("--dims", type=int, default=256)
    ap.add_argument("--json", type=Path, default=None, help="write the full per-query result here")
    ap.add_argument("--verbose", action="store_true", help="print queries whose expected note is not in the top 3")
    a = ap.parse_args(argv)

    docs = load_corpus(a.corpus)
    queries = load_queries(a.queries)
    res = run(docs, queries, a.embed_url, a.dims)
    rows = res["rows"]
    print(f"corpus={res['n_docs']} notes  queries={res['n_queries']}  embed={'yes' if a.embed_url else 'no'}")
    for mode in MODES:
        for kind in (None, "nl", "kw"):
            s = summarize(rows, mode, kind)
            if s:
                label = kind or "all"
                print(f"{mode:8s} {label:4s} n={s['n']:<3d} hit@3={s['hit@3']:.3f} mrr@10={s['mrr@10']:.3f}")
    cos = [r for r in rows if r["expect_cos"] is not None]
    if cos:
        hits = [r["expect_cos"] for r in cos]
        others = [r["best_other_cos"] for r in cos if r["best_other_cos"] is not None]
        print(f"vector cosine: expected note {min(hits):.3f}..{max(hits):.3f}; "
              f"best non-expected note {min(others):.3f}..{max(others):.3f}")
    if a.verbose:
        for r in rows:
            for mode, rank in r["ranks"].items():
                if rank is None or rank > 3:
                    print(f"  miss {mode} rank={rank} [{r['kind']}] {r['q']!r} -> {r['expect']}")
    if a.json:
        a.json.parent.mkdir(parents=True, exist_ok=True)
        a.json.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
