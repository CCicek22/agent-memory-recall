from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
import conftest  # noqa: F401  (puts eval/ on sys.path)
from metrics import hit_at, mrr_at, rank_of
from retrieval import bm25_scores, cosine, rank_by_scores, rrf_fuse, tokenize, vector_scores
import run_eval


def test_rank_of_is_one_based_and_none_when_absent() -> None:
    assert rank_of("b", ["a", "b", "c"]) == 2
    assert rank_of("z", ["a", "b"]) is None


def test_hit_at_and_mrr_on_fixture() -> None:
    ranks = [1, 2, None, 5, 12]  # 12 is outside the top 10
    assert hit_at(ranks, 1) == pytest.approx(0.2)
    assert hit_at(ranks, 3) == pytest.approx(0.4)
    assert mrr_at(ranks, 10) == pytest.approx((1 + 0.5 + 0.2) / 5)
    assert mrr_at(ranks, 12) == pytest.approx((1 + 0.5 + 0.2 + 1 / 12) / 5)


def test_metrics_on_empty_input_are_zero() -> None:
    assert hit_at([], 3) == 0.0 and mrr_at([], 10) == 0.0


def test_cosine_identity_and_orthogonal() -> None:
    assert cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_vector_scores_and_ranking_tie_break() -> None:
    s = vector_scores([1.0, 0.0], {"b": [1.0, 0.0], "a": [1.0, 0.0], "c": [0.0, 1.0]})
    assert rank_by_scores(s) == ["a", "b", "c"]


def test_bm25_prefers_the_document_with_the_term() -> None:
    docs = {"x": "retry the request with backoff", "y": "pin the lockfile", "z": "rotate keys"}
    s = bm25_scores("backoff retry", docs)
    assert rank_by_scores(s)[0] == "x"
    assert s["y"] == 0.0


def test_tokenize_drops_stopwords() -> None:
    assert tokenize("What is the Backoff?") == ["backoff"]


def test_rrf_fuse_rewards_agreement() -> None:
    fused = rrf_fuse([["a", "b", "c"], ["b", "a", "d"]], k=60)
    assert rank_by_scores(fused)[:2] == ["a", "b"]
    assert fused["a"] == pytest.approx(1 / 61 + 1 / 62)


def test_demo_data_is_consistent() -> None:
    corpus = {p.stem for p in (ROOT / "eval" / "corpus").glob("*.md")}
    rows = [json.loads(l) for l in (ROOT / "eval" / "queries.jsonl").read_text().splitlines()]
    assert len(corpus) == 40 and len(rows) == 40
    assert sum(r["kind"] == "nl" for r in rows) == 30 and sum(r["kind"] == "kw" for r in rows) == 10
    assert {r["expect"] for r in rows} == corpus


def test_runner_keyword_mode_end_to_end(tmp_path: Path, capsys) -> None:
    corpus = tmp_path / "c"
    corpus.mkdir()
    (corpus / "alpha.md").write_text("cache keys must include the lockfile hash")
    (corpus / "beta.md").write_text("retry with backoff and jitter")
    q = tmp_path / "q.jsonl"
    q.write_text(json.dumps({"q": "lockfile cache", "kind": "kw", "expect": "alpha"}) + "\n"
                 + json.dumps({"q": "backoff jitter", "kind": "nl", "expect": "beta"}) + "\n")
    out = tmp_path / "res.json"
    assert run_eval.main(["--corpus", str(corpus), "--queries", str(q), "--json", str(out)]) == 0
    text = capsys.readouterr().out
    assert "keyword  all  n=2   hit@3=1.000" in text
    assert "vector" not in text  # no --embed-url, so no vector mode
    assert json.loads(out.read_text())["n_docs"] == 2
