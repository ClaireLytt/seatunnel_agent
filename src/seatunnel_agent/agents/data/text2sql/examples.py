"""Few-shot example store — the Text2SQL accuracy flywheel.

Verified (question, SQL) pairs are the highest-leverage context a Text2SQL
agent can get: they pin table choice, join shape and dialect quirks far
better than schema text alone. This store collects them from two sources:

- **feedback**: the user clicked 👍 on a query result (UI), confirming the
  generated SQL answered the question — saved automatically as verified.
- **manual**: curated pairs added via CLI (``t2s-examples add``) or by
  editing the JSON file directly.

Retrieval is BM25 over the questions (same tokenizer as schema retrieval),
and the top-K hits are injected into the *user message* (not the system
prompt) so they adapt per question. Storage style/limits mirror
``favorites.py``: one JSON file, atomic replace, bounded size.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from seatunnel_agent.common.json_file_store import JsonFileStore

_MAX_EXAMPLES = 500
_MAX_SQL_CHARS = 4000

_DEFAULT_EXAMPLES_PATH = os.getenv("T2S_EXAMPLES_PATH", "config/t2s_examples.json")


class ExampleStore(JsonFileStore):
    """JSON-file-backed store of verified question→SQL pairs."""

    def __init__(self, path: str | Path | None = None) -> None:
        super().__init__(
            path if path is not None else _DEFAULT_EXAMPLES_PATH,
            max_items=_MAX_EXAMPLES,
        )

    # -- persistence override -------------------------------------------

    def _read(self) -> list[dict[str, Any]]:
        # The file is hand-editable — drop malformed entries instead of
        # letting them crash retrieval/augmentation later.
        return [it for it in super()._read() if isinstance(it, dict)]

    # -- CRUD ----------------------------------------------------------

    def add(
        self,
        question: str,
        sql: str,
        tables: list[str] | None = None,
        source: str = "manual",
        verified: bool = True,
    ) -> dict[str, Any]:
        question = question.strip()
        sql = sql.strip()[:_MAX_SQL_CHARS]
        if not question or not sql:
            raise ValueError("question 和 sql 都不能为空")
        entry = {
            "id": self._make_id(),
            "question": question,
            "sql": sql,
            "tables": list(tables or []),
            "source": source,
            "verified": bool(verified),
            "created_at": self._now_iso(),
        }
        # Same question -> replace (latest confirmation wins), so a
        # re-verified pair never duplicates.
        with self._lock:
            items = self._read()
            items = [
                it for it in items
                if it.get("question", "").strip() != question
            ]
            items.append(entry)
            if len(items) > self.max_items:
                items = items[-self.max_items:]
            self._write(items)
            return entry

    def remove(self, example_id: str) -> bool:
        return self._delete_by_id(example_id)

    def remove_by_question(self, question: str) -> bool:
        """Drop the pair for ``question`` (👎 on a previously-verified answer)."""
        question = question.strip()
        with self._lock:
            items = self._read()
            kept = [
                it for it in items
                if it.get("question", "").strip() != question
            ]
            if len(kept) == len(items):
                return False
            self._write(kept)
            return True

    # -- retrieval -----------------------------------------------------

    def top(self, question: str, k: int = 3) -> list[dict[str, Any]]:
        """BM25 top-K verified examples for ``question`` (score > 0 only)."""
        items = [
            it for it in self._read()
            if it.get("verified") and it.get("question") and it.get("sql")
        ]
        if not items or not question.strip():
            return []
        from .retrieval import BM25, _doc_tokens

        bm25 = BM25([_doc_tokens(it.get("question", "")) for it in items])
        scores = bm25.scores(_doc_tokens(question))
        ranked = sorted(
            (
                (s, it) for s, it in zip(scores, items)
                if s > 0
            ),
            key=lambda pair: pair[0],
            reverse=True,
        )
        return [it for _s, it in ranked[:k]]


def augment_question(question: str, store: ExampleStore | None, k: int = 3) -> str:
    """Append the top-K verified examples to the user question as reference
    context. Returns ``question`` unchanged when nothing matches — the
    example store is strictly opt-in and additive."""
    if store is None:
        return question
    try:
        hits = store.top(question, k=k)
        if not hits:
            return question
        lines = [
            question,
            "",
            "[参考示例 — 此前已被用户确认正确的 问题→SQL 对，供风格与表选择参考；"
            "仍须遵守全部硬规则（指标口径、白名单、分区过滤）]",
        ]
        for it in hits:
            lines.append(f"Q: {it.get('question', '')}")
            lines.append(f"SQL: {it.get('sql', '')}")
            lines.append("")
        return "\n".join(lines).rstrip()
    except Exception:
        return question  # examples must never break the chat
