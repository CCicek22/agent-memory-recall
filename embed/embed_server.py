"""Local text-embedding server with an OpenAI-style /v1/embeddings endpoint.

Loads a sentence-transformers model on first use and unloads it after IDLE_TIMEOUT seconds
without requests, so the GPU or RAM is free between prompts.

Env:
  EMBED_HOST (127.0.0.1)  EMBED_PORT (8790)  EMBED_MODEL (google/embeddinggemma-2)
  EMBED_IDLE_TIMEOUT (3600)  EMBED_DEFAULT_DIMS (256)
GET  /health
POST /v1/embeddings   {"input": str | [str], "dimensions": 128|256|512|768, "encoding_format": "float"|"base64"}

Never use float16 for this model: activations can overflow silently (see the model card).
Requires the `embed` extra: uv sync --extra embed
"""
from __future__ import annotations

import base64
import gc
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import numpy as np

HOST = os.environ.get("EMBED_HOST", "127.0.0.1")
PORT = int(os.environ.get("EMBED_PORT", "8790"))
MODEL_ID = os.environ.get("EMBED_MODEL", "google/embeddinggemma-2")
IDLE_TIMEOUT = float(os.environ.get("EMBED_IDLE_TIMEOUT", "3600"))
DEFAULT_DIMS = int(os.environ.get("EMBED_DEFAULT_DIMS", "256"))
DIMS = (128, 256, 512, 768)  # Matryoshka truncation sizes the model supports
MAX_BODY = 1_000_000  # bytes; a larger request is refused before parsing


def log(msg: str) -> None:
    print(f"[embed] {time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}", file=sys.stderr, flush=True)


def parse_request(body: dict[str, Any]) -> tuple[list[str], int, str]:
    inp = body.get("input")
    texts = [inp] if isinstance(inp, str) else inp
    if not isinstance(texts, list) or not texts or not all(isinstance(t, str) for t in texts):
        raise ValueError("input must be a non-empty string or list of strings")
    dims = int(body.get("dimensions") or DEFAULT_DIMS)
    if dims not in DIMS:
        raise ValueError(f"dimensions must be one of {DIMS}")
    fmt = body.get("encoding_format") or "float"
    if fmt not in ("float", "base64"):
        raise ValueError("encoding_format must be float or base64")
    return texts, dims, fmt


def truncate_normalize(m: np.ndarray, dims: int) -> np.ndarray:
    t = np.asarray(m, np.float32)[:, :dims]
    return t / np.linalg.norm(t, axis=1, keepdims=True)


def embeddings_response(vecs: np.ndarray, fmt: str, model: str) -> dict[str, Any]:
    data = [{"object": "embedding", "index": i,
             "embedding": base64.b64encode(np.asarray(v, "<f4").tobytes()).decode() if fmt == "base64"
             else [float(x) for x in v]}
            for i, v in enumerate(vecs)]
    n = int(vecs.shape[0])
    return {"object": "list", "data": data, "model": model,
            "usage": {"prompt_tokens": n, "total_tokens": n}}


def _default_loader() -> Any:
    from sentence_transformers import SentenceTransformer
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if device == "cuda" else torch.float32
    return SentenceTransformer(MODEL_ID, device=device, model_kwargs={"torch_dtype": dtype})


class Engine:
    def __init__(self, loader: Any = _default_loader) -> None:
        self._loader = loader
        self._model: Any = None
        self._lock = threading.Lock()
        self._last = time.monotonic()

    def encode(self, texts: list[str], dims: int) -> np.ndarray:
        with self._lock:
            if self._model is None:
                t = time.monotonic()
                self._model = self._loader()
                log(f"loaded {MODEL_ID} in {time.monotonic() - t:.1f}s")
            self._last = time.monotonic()
            v = self._model.encode(texts, batch_size=8, normalize_embeddings=True, convert_to_numpy=True)
        return truncate_normalize(np.atleast_2d(v), dims)

    def maybe_unload(self) -> None:
        with self._lock:
            if self._model is not None and time.monotonic() - self._last >= IDLE_TIMEOUT:
                self._model = None
                gc.collect()  # the model holds reference cycles; without this the weights stay resident
                log(f"idle {IDLE_TIMEOUT:.0f}s -> unloaded")

    def health(self) -> dict[str, Any]:
        return {"loaded": self._model is not None, "idle_s": round(time.monotonic() - self._last, 1),
                "model": MODEL_ID}


ENGINE = Engine()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass

    def _send(self, code: int, obj: dict[str, Any]) -> None:
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, ENGINE.health())
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > MAX_BODY:
                return self._send(413, {"error": {"message": "request body too large"}})
            body = json.loads(self.rfile.read(length) or b"{}")
            if self.path != "/v1/embeddings":
                return self._send(404, {"error": "not found"})
            texts, dims, fmt = parse_request(body)
            vecs = ENGINE.encode(texts, dims)
            self._send(200, embeddings_response(vecs, fmt, body.get("model") or MODEL_ID))
        except ValueError as e:  # includes json.JSONDecodeError
            self._send(400, {"error": {"message": str(e)}})
        except Exception as e:
            log(f"500 {type(e).__name__}: {e}")
            self._send(500, {"error": {"message": f"{type(e).__name__}: {e}"}})


def main() -> None:
    def watcher() -> None:
        while True:
            time.sleep(60)
            ENGINE.maybe_unload()

    threading.Thread(target=watcher, daemon=True).start()
    log(f"listening {HOST}:{PORT} model={MODEL_ID} idle={IDLE_TIMEOUT:.0f}s")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
