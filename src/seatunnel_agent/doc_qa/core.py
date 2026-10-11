# -*- coding: utf-8 -*-
"""Doc Q&A core — BM25 retrieval over local docs, zero dependencies.

Corpus = the project's ``docs/*.md`` (recursive) plus the built-in connector
docs rendered to text, chunked to ~60 lines.  Tokenization handles both
scripts: ASCII words lowered, CJK as character bigrams.  Everything is
offline and deterministic; the optional LLM synthesis lives in answer.py.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

_CHUNK_LINES = 60
_ASCII_TOKEN = re.compile(r"[a-z0-9_.]{2,}")
_CJK = re.compile(r"[一-鿿]")


@dataclass
class Chunk:
    source: str          # file path or "connector:Jdbc"
    title: str
    text: str
    tokens: Counter = field(default_factory=Counter)


def tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    tokens = _ASCII_TOKEN.findall(text)
    cjk = _CJK.findall(text)
    tokens += ["".join(p) for p in zip(cjk, cjk[1:])] or cjk[:1]
    return tokens


class BM25Index:
    """Plain BM25 (k1=1.5, b=0.75) over pre-tokenized chunks."""

    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        for c in chunks:
            c.tokens = Counter(tokenize(f"{c.title}\n{c.text}"))
        self.doc_len = [sum(c.tokens.values()) for c in chunks]
        self.avg_len = (sum(self.doc_len) / len(chunks)) if chunks else 0.0
        self.df: Counter = Counter()
        for c in chunks:
            self.df.update(c.tokens.keys())
        self.n = len(chunks)

    def _idf(self, term: str) -> float:
        df = self.df.get(term, 0)
        return math.log(1 + (self.n - df + 0.5) / (df + 0.5))

    def search(self, query: str, k: int = 4) -> list[tuple[Chunk, float]]:
        k1, b = 1.5, 0.75
        q_terms = tokenize(query)
        scored: list[tuple[Chunk, float]] = []
        for i, c in enumerate(self.chunks):
            score = 0.0
            dl = self.doc_len[i] or 1
            for term in q_terms:
                tf = c.tokens.get(term, 0)
                if not tf:
                    continue
                score += self._idf(term) * (tf * (k1 + 1)) / (
                    tf + k1 * (1 - b + b * dl / self.avg_len))
            if score > 0:
                scored.append((c, score))
        scored.sort(key=lambda t: -t[1])
        return scored[:k]


def _chunk_markdown(path: Path, rel: str) -> list[Chunk]:
    try:
        lines = path.read_text(encoding="utf-8",
                               errors="replace").splitlines()
    except OSError:
        return []
    chunks: list[Chunk] = []
    title = path.stem
    buf: list[str] = []
    for line in lines:
        if line.startswith("#"):
            title = line.lstrip("# ").strip() or title
        buf.append(line)
        if len(buf) >= _CHUNK_LINES:
            chunks.append(Chunk(source=rel, title=title,
                                text="\n".join(buf)))
            buf = []
    if buf:
        chunks.append(Chunk(source=rel, title=title, text="\n".join(buf)))
    return chunks


def _connector_chunks() -> list[Chunk]:
    from ..connector_docs import CONNECTOR_DOCS
    chunks = []
    for key, doc in CONNECTOR_DOCS.items():
        lines = [f"# {doc.name} ({doc.connector_type})", doc.description, ""]
        for p in list(doc.required_params) + list(doc.optional_params):
            req = "required" if p.required else "optional"
            enum = f" 可选值: {', '.join(p.enum_values)}" if p.enum_values else ""
            lines.append(f"- {p.name} ({p.type}, {req}): {p.description}"
                         f" 示例: {p.example}{enum}")
        lines += [""] + [f"> {n}" for n in doc.notes]
        chunks.append(Chunk(source=f"connector:{key}",
                            title=f"{doc.name} connector",
                            text="\n".join(lines)))
    return chunks


def build_corpus(docs_dir: str | Path | None = "docs") -> list[Chunk]:
    """Connector docs always; *docs_dir* markdown when it exists."""
    chunks = _connector_chunks()
    if docs_dir:
        root = Path(docs_dir)
        if root.is_dir():
            for f in sorted(root.rglob("*.md")):
                chunks.extend(_chunk_markdown(f, str(f)))
    return chunks


_INDEX_CACHE: dict[str, BM25Index] = {}


def get_index(docs_dir: str | Path | None = "docs") -> BM25Index:
    key = str(docs_dir or "")
    if key not in _INDEX_CACHE:
        _INDEX_CACHE[key] = BM25Index(build_corpus(docs_dir))
    return _INDEX_CACHE[key]
