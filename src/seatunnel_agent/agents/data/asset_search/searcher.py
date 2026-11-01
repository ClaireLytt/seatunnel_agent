"""Deterministic natural-language search over a data-asset catalog.

The catalog comes in as a JSON list ({table, comment, columns:[{name,
comment}]}) or as Hive-style CREATE TABLE DDL with COMMENT clauses.  The
query is tokenized (ASCII words plus CJK bigrams), expanded through a
small built-in synonym table (订单→order, 用户→user, …), and every asset
is scored by weighted matches — table name > table comment > column name
> column comment — with the hits reported, so the ranking is explainable
and reproducible.  An optional LLM pass can rerank or explain; the
deterministic list is the contract.  No database connection.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

__all__ = ["Asset", "SearchHit", "SearchResult", "parse_catalog",
           "search_assets"]

# query-term expansion: zh term -> extra en tokens (and the reverse)
_SYNONYMS: dict[str, tuple[str, ...]] = {
    "订单": ("order", "orders"),
    "用户": ("user", "users", "uid"),
    "金额": ("amount", "gmv", "price", "fee"),
    "支付": ("pay", "payment"),
    "退款": ("refund",),
    "商品": ("item", "product", "sku", "goods"),
    "日": ("daily", "day"),
    "月": ("monthly", "month"),
    "明细": ("detail", "dwd"),
    "汇总": ("summary", "agg", "dws"),
    "渠道": ("channel", "source"),
    "地址": ("address", "addr"),
    "库存": ("stock", "inventory"),
    "日志": ("log", "logs", "event"),
    "留存": ("retention",),
    "活跃": ("active", "dau", "mau"),
}

_W_TABLE_NAME = 5.0
_W_TABLE_COMMENT = 4.0
_W_COLUMN_NAME = 3.0
_W_COLUMN_COMMENT = 2.0


@dataclass
class Asset:
    table: str
    comment: str = ""
    columns: list[dict] = field(default_factory=list)  # {name, comment}

    def to_dict(self) -> dict:
        return {"table": self.table, "comment": self.comment,
                "columns": self.columns}


@dataclass
class SearchHit:
    table: str
    comment: str
    score: float
    matched_columns: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"table": self.table, "comment": self.comment,
                "score": round(self.score, 1),
                "matched_columns": self.matched_columns,
                "reasons": self.reasons}


@dataclass
class SearchResult:
    query: str
    terms: list[str]
    total_assets: int
    hits: list[SearchHit]

    def to_dict(self) -> dict:
        return {"query": self.query, "terms": self.terms,
                "total_assets": self.total_assets,
                "hits": [h.to_dict() for h in self.hits]}


_DDL_HEAD = re.compile(
    r"CREATE\s+(?:EXTERNAL\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"[`\"]?([\w.]+)[`\"]?\s*\(", re.IGNORECASE)
_DDL_TBL_COMMENT = re.compile(r"^\s*COMMENT\s+'([^']*)'", re.IGNORECASE)
_DDL_COL_COMMENT = re.compile(r"COMMENT\s+'([^']*)'", re.IGNORECASE)
_DDL_COL_NAME = re.compile(r"^\s*[`\"]?(\w+)[`\"]?\s+\S")


def _balanced_block(text: str, start: int) -> tuple[str, int]:
    """Return (inside, index after the closing paren); start is at '('."""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
    return text[start + 1:], len(text)


def _split_top_level(blob: str) -> list[str]:
    parts, depth, buf = [], 0, []
    for ch in blob:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return parts


def parse_catalog(text: str) -> list[Asset]:
    body = (text or "").strip()
    if not body:
        raise ValueError("empty catalog / 资产目录为空")
    if body.startswith("["):
        items = json.loads(body)
        assets = []
        for it in items:
            if not isinstance(it, dict) or "table" not in it:
                raise ValueError("each catalog item needs 'table' / "
                                 "目录项缺 table")
            cols = [{"name": c.get("name", ""),
                     "comment": c.get("comment", "")}
                    if isinstance(c, dict) else {"name": str(c), "comment": ""}
                    for c in it.get("columns", [])]
            assets.append(Asset(table=str(it["table"]),
                                comment=str(it.get("comment", "")),
                                columns=cols))
        if not assets:
            raise ValueError("empty catalog / 资产目录为空")
        return assets
    assets = []
    for m in _DDL_HEAD.finditer(body):
        name = m.group(1)
        cols_blob, after = _balanced_block(body, m.end() - 1)
        tc = _DDL_TBL_COMMENT.match(body[after:])
        columns = []
        for line in _split_top_level(cols_blob):
            line = line.strip()
            nm = _DDL_COL_NAME.match(line)
            if not nm or nm.group(1).upper() in ("PRIMARY", "KEY",
                                                 "CONSTRAINT", "UNIQUE"):
                continue
            cm = _DDL_COL_COMMENT.search(line)
            columns.append({"name": nm.group(1),
                            "comment": cm.group(1) if cm else ""})
        assets.append(Asset(table=name, comment=tc.group(1) if tc else "",
                            columns=columns))
    if not assets:
        raise ValueError("no CREATE TABLE found / 没有可解析的建表语句")
    return assets


def _terms(query: str) -> list[str]:
    q = (query or "").strip().lower()
    terms: list[str] = re.findall(r"[a-z0-9_]+", q)
    cjk = re.findall(r"[一-鿿]+", q)
    for run in cjk:
        if len(run) == 1:
            terms.append(run)
        terms.extend(run[i:i + 2] for i in range(len(run) - 1))
    expanded = list(terms)
    for t in terms:
        for zh, ens in _SYNONYMS.items():
            if t == zh or t in ens:
                expanded.extend([zh, *ens])
    # dedupe, keep order
    seen: set[str] = set()
    out = []
    for t in expanded:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def search_assets(assets: list[Asset], query: str,
                  limit: int = 10) -> SearchResult:
    terms = _terms(query)
    if not terms:
        raise ValueError("empty query / 查询为空")
    hits: list[SearchHit] = []
    for a in assets:
        score = 0.0
        reasons: list[str] = []
        matched_cols: list[str] = []
        tbl = a.table.lower()
        cmt = a.comment.lower()
        for t in terms:
            if t in tbl:
                score += _W_TABLE_NAME
                reasons.append(f"table~{t}")
            if cmt and t in cmt:
                score += _W_TABLE_COMMENT
                reasons.append(f"comment~{t}")
        for col in a.columns:
            cname = col["name"].lower()
            ccmt = (col.get("comment") or "").lower()
            col_hit = False
            for t in terms:
                if t in cname:
                    score += _W_COLUMN_NAME
                    col_hit = True
                elif ccmt and t in ccmt:
                    score += _W_COLUMN_COMMENT
                    col_hit = True
            if col_hit and col["name"] not in matched_cols:
                matched_cols.append(col["name"])
        if score > 0:
            hits.append(SearchHit(table=a.table, comment=a.comment,
                                  score=score,
                                  matched_columns=matched_cols[:6],
                                  reasons=sorted(set(reasons))[:6]))
    hits.sort(key=lambda h: (-h.score, h.table))
    return SearchResult(query=query.strip(), terms=terms,
                        total_assets=len(assets), hits=hits[:limit])
