# -*- coding: utf-8 -*-
"""Answering layer: extractive by default, optional LLM synthesis.

The extractive answer (top chunks + citations) is always produced and never
needs a key; the LLM pass rewrites it into a direct answer **grounded in the
retrieved chunks only** and falls back to the extractive version on any
failure."""

from __future__ import annotations

from typing import Any, Callable

from .core import BM25Index, Chunk


def normalize_lang(lang: str | None) -> str:
    return "en" if (lang or "").lower().startswith("en") else "zh"


_I18N = {
    "en": {
        "title": "## Doc Q&A",
        "no_hit": ("No matching passage in the indexed docs — try different "
                   "keywords (connector names work well: Jdbc, Kafka, "
                   "MySQL-CDC …)."),
        "sources": "### Sources",
        "excerpt": "Relevant excerpts",
        "llm_failed": "> ⚠️ LLM synthesis failed ({err}) — showing excerpts.",
    },
    "zh": {
        "title": "## 文档问答",
        "no_hit": ("索引里没有匹配的段落 — 换个关键词试试(连接器名效果"
                   "最好:Jdbc、Kafka、MySQL-CDC…)。"),
        "sources": "### 来源",
        "excerpt": "相关片段",
        "llm_failed": "> ⚠️ LLM 综合失败({err})— 以下为检索片段。",
    },
}

_SYSTEM = (
    "Answer the user's question using ONLY the provided documentation "
    "excerpts. Cite the source labels like [1]. If the excerpts do not "
    "contain the answer, say so — never invent parameters or defaults. "
    "Answer in the user's language.")


def _excerpt(text: str, limit: int = 700) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + "\n…"


def extractive_markdown(question: str, hits: list[tuple[Chunk, float]],
                        lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    t = _I18N[lang]
    lines = [t["title"], ""]
    if not hits:
        lines.append(t["no_hit"])
        return "\n".join(lines)
    lines.append(f"**Q:** {question}")
    lines += ["", f"### {t['excerpt']}"]
    for i, (chunk, _score) in enumerate(hits, 1):
        lines += ["", f"**[{i}] {chunk.title}** — `{chunk.source}`", "",
                  _excerpt(chunk.text)]
    lines += ["", t["sources"]]
    for i, (chunk, score) in enumerate(hits, 1):
        lines.append(f"{i}. `{chunk.source}` (score {score:.2f})")
    return "\n".join(lines)


def answer(question: str, index: BM25Index, k: int = 4, lang: str = "zh",
           use_llm: bool = False,
           client_factory: Callable | None = None) -> dict[str, Any]:
    """{'markdown', 'hits': [{source, title, score}]} — never raises."""
    lang = normalize_lang(lang)
    hits = index.search(question, k=k)
    md = extractive_markdown(question, hits, lang)
    if use_llm and hits:
        context = "\n\n".join(
            f"[{i}] {c.title} ({c.source})\n{_excerpt(c.text, 1500)}"
            for i, (c, _s) in enumerate(hits, 1))
        try:
            if client_factory is None:
                from ..config import load_settings
                from ..llm import LLMClient
                client = LLMClient(load_settings(), agent="doc_qa")
            else:
                client = client_factory(None)
            resp = client.chat(_SYSTEM, [{
                "role": "user",
                "content": f"QUESTION:\n{question}\n\nEXCERPTS:\n{context}"}])
            reply = (resp.reply_text or "").strip()
            if reply:
                cite = "\n".join(
                    f"{i}. `{c.source}`"
                    for i, (c, _s) in enumerate(hits, 1))
                md = (f"{_I18N[lang]['title']}\n\n{reply}\n\n"
                      f"{_I18N[lang]['sources']}\n{cite}")
        except Exception as exc:  # noqa: BLE001 — synthesis is advisory
            md = (_I18N[lang]["llm_failed"].format(
                err=f"{type(exc).__name__}: {exc}") + "\n\n" + md)
    return {"markdown": md,
            "hits": [{"source": c.source, "title": c.title,
                      "score": round(s, 3)} for c, s in hits]}
