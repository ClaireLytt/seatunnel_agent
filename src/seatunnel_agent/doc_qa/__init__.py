# -*- coding: utf-8 -*-
"""Doc Q&A — offline BM25 retrieval over project + connector docs, with
optional grounded LLM synthesis."""

from .answer import answer, extractive_markdown
from .core import BM25Index, Chunk, build_corpus, get_index, tokenize

__all__ = [
    "BM25Index",
    "Chunk",
    "answer",
    "build_corpus",
    "extractive_markdown",
    "get_index",
    "tokenize",
]
