"""Hybrid schema retrieval — keyword × BM25 × optional vectors (PRD §5).

The existing keyword scorer (:mod:`matcher`) is precise on English
identifiers but degrades on large schemas and paraphrased Chinese
questions. This module fuses three channels, each normalized to [0,1]
per query by its max score:

    score = w_kw · keyword + w_bm25 · BM25 + w_vec · vector

- **keyword**: the existing ``matcher`` scoring, kept as the precision
  anchor and tie-breaker (zero behavior change when the other channels
  are disabled and weights collapse onto it).
- **BM25**: pure-Python Okapi BM25 over one document per table
  (name + comment + column names/comments). No dependencies.
- **vector**: optional; embeddings come from an OpenAI-compatible
  ``/embeddings`` endpoint configured by ``EMBEDDING_MODEL`` (+ optional
  ``EMBEDDING_BASE_URL``, ``EMBEDDING_API_KEY``). Unset = disabled, and
  any runtime failure degrades to the other channels for the session.
  Document vectors are cached in ``logs/.t2s_index/`` keyed by the
  schema content hash, so re-connects never re-bill.

Weights: ``T2S_RETRIEVAL_WEIGHTS=kw,bm25,vec`` (default 0.4,0.3,0.3;
without vectors the remaining two renormalize to 0.55/0.45 behavior).
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .matcher import TableMatch, _score_table, tokenize
from .schema import SchemaStore, TableSchema

logger = logging.getLogger(__name__)

_INDEX_DIR = Path("logs") / ".t2s_index"

_SNAKE_SPLIT_RE = re.compile(r"[a-zA-Z]+|\d+")
_ENGLISH_TOKEN_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")
_CJK_RUN_RE = re.compile(r"[一-鿿]+")

# BM25 hyperparameters (standard Okapi defaults).
_K1 = 1.5
_B = 0.75


def _doc_tokens(text: str) -> list[str]:
    """Tokenize a document/query for BM25: English identifiers plus their
    snake_case parts, and CJK bigrams (fixed n=2 keeps IDF meaningful)."""
    tokens: list[str] = []
    for ident in _ENGLISH_TOKEN_RE.findall(text):
        low = ident.lower()
        tokens.append(low)
        parts = [p.lower() for p in _SNAKE_SPLIT_RE.findall(ident)]
        if len(parts) > 1:
            tokens.extend(parts)
    for run in _CJK_RUN_RE.findall(text):
        if len(run) == 1:
            tokens.append(run)
        for i in range(len(run) - 1):
            tokens.append(run[i:i + 2])
    return tokens


def table_document(table: TableSchema) -> str:
    """The retrieval document for one table."""
    parts = [table.full_name, table.comment]
    for col in table.columns + table.partition_columns:
        parts.append(col.name)
        parts.append(col.comment)
    return " ".join(p for p in parts if p)


class BM25:
    """Okapi BM25 over pre-tokenized documents. Deterministic, no deps."""

    def __init__(self, docs: list[list[str]]) -> None:
        self._doc_count = len(docs)
        self._doc_len = [len(d) for d in docs]
        self._avgdl = (sum(self._doc_len) / self._doc_count) if docs else 0.0
        self._tf: list[dict[str, int]] = []
        df: dict[str, int] = {}
        for tokens in docs:
            counts: dict[str, int] = {}
            for tok in tokens:
                counts[tok] = counts.get(tok, 0) + 1
            self._tf.append(counts)
            for tok in counts:
                df[tok] = df.get(tok, 0) + 1
        self._idf = {
            tok: math.log((self._doc_count - n + 0.5) / (n + 0.5) + 1.0)
            for tok, n in df.items()
        }

    def scores(self, query_tokens: list[str]) -> list[float]:
        out = [0.0] * self._doc_count
        if not self._doc_count:
            return out
        for i in range(self._doc_count):
            tf = self._tf[i]
            dl = self._doc_len[i] or 1
            norm = _K1 * (1 - _B + _B * dl / (self._avgdl or 1))
            s = 0.0
            for tok in query_tokens:
                f = tf.get(tok)
                if not f:
                    continue
                s += self._idf.get(tok, 0.0) * f * (_K1 + 1) / (f + norm)
            out[i] = s
        return out


# ----------------------------------------------------------------------
# Optional embedding channel
# ----------------------------------------------------------------------


def _embedding_config() -> tuple[str, str, str] | None:
    """(model, base_url, api_key) or None when disabled."""
    model = os.getenv("EMBEDDING_MODEL", "").strip()
    if not model:
        return None
    base = os.getenv("EMBEDDING_BASE_URL", "").strip() \
        or os.getenv("LLM_BASE_URL", "").strip() \
        or "https://api.openai.com/v1"
    key = os.getenv("EMBEDDING_API_KEY", "").strip() \
        or os.getenv("API_KEY", "").strip() \
        or os.getenv("ANTHROPIC_API_KEY", "").strip()
    return model, base.rstrip("/"), key


def _embed_texts(texts: list[str], model: str, base: str, key: str,
                 timeout: int = 60) -> list[list[float]]:
    """Call an OpenAI-compatible /embeddings endpoint (stdlib only)."""
    import urllib.request

    payload = json.dumps({"model": model, "input": texts}).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/embeddings",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    items = sorted(data["data"], key=lambda d: d.get("index", 0))
    return [item["embedding"] for item in items]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if not na or not nb:
        return 0.0
    return dot / (na * nb)


def schema_hash(store: SchemaStore) -> str:
    """Content hash of the schema — the persistence key for doc vectors."""
    text = "\n".join(sorted(table_document(t) for t in store.tables))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _parse_weights() -> tuple[float, float, float]:
    raw = os.getenv("T2S_RETRIEVAL_WEIGHTS", "").strip()
    if raw:
        try:
            parts = [float(x) for x in raw.split(",")]
            if len(parts) == 3 and all(p >= 0 for p in parts) and sum(parts) > 0:
                return parts[0], parts[1], parts[2]
        except ValueError:
            pass
        logger.warning("Invalid T2S_RETRIEVAL_WEIGHTS=%r; using defaults", raw)
    return 0.4, 0.3, 0.3


def metric_document(metric) -> str:
    """The retrieval document for one metric definition."""
    parts = [metric.name, metric.display_name, *metric.aliases,
             metric.description]
    if not metric.is_ratio:
        parts.append(metric.expression)
    return " ".join(p for p in parts if p)


@dataclass
class HybridRetriever:
    """Fused table (and metric) ranking. Build once per schema; rank per
    question."""

    store: SchemaStore
    metric_store: object = None  # optional MetricStore for rank_metrics
    index_dir: Path = field(default_factory=lambda: _INDEX_DIR)
    embed_fn: object = None  # test hook: (texts) -> vectors; None = env config

    def __post_init__(self) -> None:
        self._tables = self.store.tables
        self._docs = [table_document(t) for t in self._tables]
        self._bm25 = BM25([_doc_tokens(d) for d in self._docs])
        self._hash = schema_hash(self.store)
        self._doc_vectors: list[list[float]] | None = None
        self._vector_failed = False
        # metric channel (optional)
        self._metrics = list(self.metric_store.metrics) if (
            self.metric_store is not None and len(self.metric_store)
        ) else []
        self._metric_docs = [metric_document(m) for m in self._metrics]
        self._metric_bm25 = BM25([_doc_tokens(d) for d in self._metric_docs])
        if self._metric_docs:
            text = "\n".join(sorted(self._metric_docs))
            self._metric_hash = hashlib.sha256(
                text.encode("utf-8")).hexdigest()[:16]
        else:
            self._metric_hash = ""
        self._metric_vectors: list[list[float]] | None = None

    # -- vector channel ------------------------------------------------

    def _embedder(self):
        """(fn(texts)->vectors, cache_tag) or None when disabled."""
        if self.embed_fn is not None:
            return self.embed_fn, "test"
        cfg = _embedding_config()
        if cfg is None:
            return None
        model, base, key = cfg
        return (
            lambda texts: _embed_texts(texts, model, base, key),
            model,
        )

    def _cache_path(self, tag: str) -> Path:
        safe_tag = re.sub(r"[^\w.-]", "_", tag)
        return self.index_dir / f"{self._hash}.{safe_tag}.emb.json"

    def _load_doc_vectors(self) -> list[list[float]] | None:
        if self._vector_failed:
            return None
        if self._doc_vectors is not None:
            return self._doc_vectors
        embedder = self._embedder()
        if embedder is None:
            return None
        fn, tag = embedder
        cache = self._cache_path(tag)
        if cache.is_file():
            try:
                data = json.loads(cache.read_text(encoding="utf-8"))
                if len(data.get("vectors", [])) == len(self._docs):
                    self._doc_vectors = data["vectors"]
                    return self._doc_vectors
            except (json.JSONDecodeError, OSError):
                pass  # corrupt cache — rebuild
        try:
            vectors = fn(self._docs)
        except Exception as exc:
            logger.warning("Embedding channel disabled for this session: %s", exc)
            self._vector_failed = True
            return None
        try:
            self.index_dir.mkdir(parents=True, exist_ok=True)
            cache.write_text(
                json.dumps({"schema_hash": self._hash, "vectors": vectors}),
                encoding="utf-8",
            )
        except OSError:
            pass  # cache is best-effort
        self._doc_vectors = vectors
        return vectors

    def _load_metric_vectors(self) -> list[list[float]] | None:
        if self._vector_failed or not self._metric_docs:
            return None
        if self._metric_vectors is not None:
            return self._metric_vectors
        embedder = self._embedder()
        if embedder is None:
            return None
        fn, tag = embedder
        safe_tag = re.sub(r"[^\w.-]", "_", tag)
        cache = self.index_dir / f"{self._metric_hash}.{safe_tag}.m.emb.json"
        if cache.is_file():
            try:
                data = json.loads(cache.read_text(encoding="utf-8"))
                if len(data.get("vectors", [])) == len(self._metric_docs):
                    self._metric_vectors = data["vectors"]
                    return self._metric_vectors
            except (json.JSONDecodeError, OSError):
                pass
        try:
            vectors = fn(self._metric_docs)
        except Exception as exc:
            logger.warning("Embedding channel disabled for this session: %s", exc)
            self._vector_failed = True
            return None
        try:
            self.index_dir.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps({"vectors": vectors}), encoding="utf-8")
        except OSError:
            pass
        self._metric_vectors = vectors
        return vectors

    def _query_vector(self, query: str) -> list[float] | None:
        embedder = self._embedder()
        if embedder is None or self._vector_failed:
            return None
        fn, _tag = embedder
        try:
            return fn([query])[0]
        except Exception as exc:
            logger.warning("Embedding channel disabled for this session: %s", exc)
            self._vector_failed = True
            return None

    def _vector_scores(self, query: str) -> list[float] | None:
        doc_vectors = self._load_doc_vectors()
        if doc_vectors is None:
            return None
        qvec = self._query_vector(query)
        if qvec is None:
            return None
        return [_cosine(qvec, dv) for dv in doc_vectors]

    # -- fusion ----------------------------------------------------------

    @staticmethod
    def _max_norm(scores: list[float]) -> list[float]:
        top = max(scores) if scores else 0.0
        if top <= 0:
            return [0.0] * len(scores)
        return [s / top for s in scores]

    def rank(self, query: str, top_n: int = 5) -> list[TableMatch]:
        """Fused ranking; returns matcher-compatible TableMatch objects
        (keyword-channel hit details, fused score in [0,1])."""
        if not self._tables:
            return []
        english, ngrams = tokenize(query)
        keyword_matches = [
            _score_table(t, english, ngrams) for t in self._tables
        ]
        kw = self._max_norm([m.score for m in keyword_matches])
        bm = self._max_norm(self._bm25.scores(_doc_tokens(query)))
        vec_raw = self._vector_scores(query)

        w_kw, w_bm, w_vec = _parse_weights()
        if vec_raw is None:
            total = w_kw + w_bm
            w_kw, w_bm, w_vec = w_kw / total, w_bm / total, 0.0
            vec = [0.0] * len(self._tables)
        else:
            vec = self._max_norm(vec_raw)

        fused: list[TableMatch] = []
        for i, m in enumerate(keyword_matches):
            score = w_kw * kw[i] + w_bm * bm[i] + w_vec * vec[i]
            if score <= 0:
                continue
            m.score = round(score, 6)
            fused.append(m)
        fused.sort(key=lambda m: (m.score, m.column_hit_count), reverse=True)
        return fused[:top_n]

    def rank_metrics(self, query: str, top_n: int = 5) -> list:
        """Fused metric ranking (MetricMatch objects, fused score in [0,1]).
        Falls back to the MetricStore's own keyword scoring when this
        retriever was built without a metric store."""
        if not self._metrics:
            return []
        english, ngrams = tokenize(query)
        keyword = [
            self.metric_store._score(m, query, english, ngrams)
            for m in self._metrics
        ]
        kw = self._max_norm([r.score for r in keyword])
        bm = self._max_norm(self._metric_bm25.scores(_doc_tokens(query)))

        vec_raw: list[float] | None = None
        metric_vectors = self._load_metric_vectors()
        if metric_vectors is not None:
            qvec = self._query_vector(query)
            if qvec is not None:
                vec_raw = [_cosine(qvec, dv) for dv in metric_vectors]

        w_kw, w_bm, w_vec = _parse_weights()
        if vec_raw is None:
            total = w_kw + w_bm
            w_kw, w_bm, w_vec = w_kw / total, w_bm / total, 0.0
            vec = [0.0] * len(self._metrics)
        else:
            vec = self._max_norm(vec_raw)

        fused = []
        for i, r in enumerate(keyword):
            score = w_kw * kw[i] + w_bm * bm[i] + w_vec * vec[i]
            if score <= 0:
                continue
            r.score = round(score, 6)
            fused.append(r)
        fused.sort(key=lambda r: r.score, reverse=True)
        return fused[:top_n]
