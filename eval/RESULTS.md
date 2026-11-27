# Retrieval results

Two sets of numbers. They are not comparable with each other.

1. **Measured on a private 30-query corpus** (author's own Basic Memory notes). Quoted from the
   author's measurement log. The notes and queries are private and are not in this repo, so these
   cannot be reproduced here. Numbers are copied as recorded; the mode names follow the log.
2. **Reproducible on the demo corpus** (`eval/corpus`, 40 synthetic notes, `eval/queries.jsonl`,
   30 natural-language + 10 keyword queries). Measured by `eval/run_eval.py` in this repo.

Metrics: hit@3 = share of queries whose expected note is in the top 3. MRR@10 = mean of 1/rank,
zero beyond rank 10.

## 1. Private corpus (quoted, not reproducible here)

Model `embeddinggemma-2`, 256 dimensions, 30 natural-language queries, index notes excluded, top 10.

| Mode (Basic Memory) | hit@3 | MRR@10 | Date |
|---|---|---|---|
| hybrid | 0.200 | 0.202 | 2026-10-07 |
| vector | 0.800 | 0.698 | 2026-10-07 |
| vector (re-run, same query set, grown index) | 0.667 | 0.559 | 2026-11-05 |

Earlier model for comparison (2026-10-07, same queries): bge-small 384d, hybrid 0.233 / 0.220,
vector 0.700 / 0.636.

Keyword queries (12, embeddinggemma-2): hybrid hit@3 0.833 / MRR 0.729; vector hit@3 0.833 / MRR 0.669.
Vector ties on hit@3 and is lower on MRR. The original log claims vector does not lose on keyword
queries; that holds for hit@3 only.

Cutoff calibration on the same model: expected-note cosine 0.768 to 0.880 (16 of 17 at or above 0.773);
off-topic cosine 0.640 to 0.769. Threshold 0.77 is set between the two. Only valid for this model.

Caveat: the 2026-11-05 query set is stale. Three of its five no-result misses point to notes that were
archived after the query was written, so those queries have no valid answer.

## 2. Demo corpus (reproducible)

Command (needs the embedding server on 127.0.0.1:8790 for the vector and fused rows):

```
python eval/run_eval.py --embed-url http://127.0.0.1:8790/v1/embeddings --dims 256 --verbose
```

Keyword-only (no server): `python eval/run_eval.py`.

Measured 2026-11-27 with `google/embeddinggemma-2` at 256 dimensions (model name read from the
server's `/health`), 40 notes, 40 queries:

| Mode | Queries | hit@3 | MRR@10 |
|---|---|---|---|
| vector | all 40 | 0.975 | 0.950 |
| vector | NL 30 | 0.967 | 0.933 |
| vector | keyword 10 | 1.000 | 1.000 |
| keyword (BM25) | all 40 | 0.875 | 0.834 |
| keyword (BM25) | NL 30 | 0.900 | 0.845 |
| keyword (BM25) | keyword 10 | 0.800 | 0.800 |
| fused (RRF of vector and BM25, k=60) | all 40 | 0.950 | 0.915 |
| fused (RRF of vector and BM25, k=60) | NL 30 | 1.000 | 0.950 |
| fused (RRF of vector and BM25, k=60) | keyword 10 | 0.800 | 0.811 |

Vector cosine on this corpus: expected note 0.709 to 0.903; best non-expected note 0.704 to 0.816.

Cutoff check on the same run (share of queries at or above a threshold):

| Threshold | Expected note kept | Best non-expected note above |
|---|---|---|
| 0.70 | 40 / 40 | 40 / 40 |
| 0.75 | 37 / 40 | 27 / 40 |
| 0.77 | 35 / 40 | 16 / 40 |

Reading: the 0.77 cutoff from the private corpus removes 5 of 40 correct notes here and does not separate
expected from off-topic notes. A cutoff has to be calibrated per model and per corpus.

Misses at vector rank above 3: one NL query (rank 14). Keyword misses are mostly NL queries with
paraphrase, and two keyword queries ("alert grouping", "profiling optimize") that match generic words in
several notes.

## What the demo does and does not show

- Vector beats keyword on this corpus, as on the private corpus. The demo corpus is small and was written by
  the same author who wrote the queries, so the gap is a weak signal, not a benchmark.
- The private-corpus finding that Basic Memory's **hybrid** mode loses to vector is **not** reproduced here.
  The reference fusion is reciprocal-rank fusion, not Basic Memory's score fusion. The hybrid result
  depends on how bm normalizes its full-text scores (see below).

## Why hybrid lost (private corpus, Basic Memory 0.23.2)

Basic Memory fuses vector and full-text scores as `max(vec, fts) + 0.3 * min(vec, fts)`, with the full-text
score normalized so its top hit is 1.0. Vector cosines from the embedding model sit between 0.64 and 0.88,
so they never beat a full-text top hit. Hybrid ranking then reduces to full-text order. This is an inference
from the formula and the observed score ranges. It was not separately instrumented, so treat it as the
likely cause, not a proven one.
