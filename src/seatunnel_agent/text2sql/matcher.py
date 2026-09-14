"""Fuzzy table/column matching for natural-language questions.

Strategy (per PRD 6.1):
- Tokenize the question into English identifiers and Chinese n-grams.
- Score every table by keyword hits against table name, table comment,
  column names and column comments.
- English name matches take priority over Chinese comment matches.
- Ties are broken by the number of column-level hits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .schema import ColumnSchema, SchemaStore, TableSchema

_ENGLISH_TOKEN_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*")
_CJK_RUN_RE = re.compile(r"[一-鿿]+")

# Generic words that appear in almost every table comment and carry no signal.
_STOPWORDS = {"数据", "信息", "查询", "统计", "明细", "记录", "表", "的",
              "select", "from", "where", "and", "or", "join", "group", "by"}

_MIN_NGRAM = 2
_MAX_NGRAM = 6


def tokenize(query: str) -> tuple[list[str], list[str]]:
    """Return (english_tokens, cjk_ngrams) extracted from the question."""
    english = [t.lower() for t in _ENGLISH_TOKEN_RE.findall(query)
               if t.lower() not in _STOPWORDS]
    ngrams: list[str] = []
    seen: set[str] = set()
    for run in _CJK_RUN_RE.findall(query):
        for size in range(_MAX_NGRAM, _MIN_NGRAM - 1, -1):
            for i in range(len(run) - size + 1):
                gram = run[i:i + size]
                if gram not in seen and gram not in _STOPWORDS:
                    seen.add(gram)
                    ngrams.append(gram)
    return english, ngrams


@dataclass
class TableMatch:
    table: TableSchema
    score: float
    name_hits: list[str] = field(default_factory=list)
    comment_hits: list[str] = field(default_factory=list)
    column_hits: list[str] = field(default_factory=list)

    @property
    def column_hit_count(self) -> int:
        return len(self.column_hits)


# Scoring weights: exact English name matches dominate, then table comment,
# then column-level signals.
_W_TABLE_NAME = 10.0
_W_TABLE_COMMENT = 3.0
_W_COLUMN_NAME = 2.0
_W_COLUMN_COMMENT = 1.0


def _score_table(table: TableSchema, english: list[str], ngrams: list[str]) -> TableMatch:
    match = TableMatch(table=table, score=0.0)
    table_lower = table.name.lower()
    full_lower = table.full_name.lower()

    for tok in english:
        if tok in (table_lower, full_lower):
            match.score += _W_TABLE_NAME * 2
            match.name_hits.append(tok)
        elif tok in table_lower:
            match.score += _W_TABLE_NAME
            match.name_hits.append(tok)

    for tok in english:
        for col in table.columns:
            if tok == col.name.lower():
                match.score += _W_COLUMN_NAME * 2
                match.column_hits.append(col.name)
            elif tok in col.name.lower() and len(tok) >= 3:
                match.score += _W_COLUMN_NAME
                match.column_hits.append(col.name)

    # CJK n-grams: longer grams matter more (length-weighted).
    for gram in ngrams:
        weight = len(gram) / _MIN_NGRAM
        if gram in table.comment:
            match.score += _W_TABLE_COMMENT * weight
            match.comment_hits.append(gram)
        for col in table.columns:
            if gram in col.comment:
                match.score += _W_COLUMN_COMMENT * weight
                match.column_hits.append(col.name)
                break  # count each gram once at column level per table
    return match


def match_tables(query: str, store: SchemaStore, top_n: int = 3) -> list[TableMatch]:
    """Rank tables by relevance to the question; ties broken by column hits."""
    english, ngrams = tokenize(query)
    matches = [_score_table(t, english, ngrams) for t in store.tables]
    matches = [m for m in matches if m.score > 0]
    matches.sort(key=lambda m: (m.score, m.column_hit_count), reverse=True)
    return matches[:top_n]


@dataclass
class ColumnMatch:
    column: ColumnSchema
    matched_by: str  # "name" or "comment"
    keyword: str


def match_columns(query: str, table: TableSchema) -> list[ColumnMatch]:
    """Map question keywords to columns. English names first, comments second."""
    english, ngrams = tokenize(query)
    results: list[ColumnMatch] = []
    seen: set[str] = set()

    for tok in english:
        for col in table.columns:
            if tok == col.name.lower() and col.name not in seen:
                seen.add(col.name)
                results.append(ColumnMatch(column=col, matched_by="name", keyword=tok))

    for gram in sorted(ngrams, key=len, reverse=True):
        for col in table.columns:
            if col.name in seen:
                continue
            if gram in col.comment:
                seen.add(col.name)
                results.append(ColumnMatch(column=col, matched_by="comment", keyword=gram))
    return results
