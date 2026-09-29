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

import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_MAX_EXAMPLES = 500
_MAX_SQL_CHARS = 4000

_DEFAULT_EXAMPLES_PATH = os.getenv("T2S_EXAMPLES_PATH", "config/t2s_examples.json")


class ExampleStore:
    """JSON-file-backed store of verified question→SQL pairs."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path if path is not None else _DEFAULT_EXAMPLES_PATH)
        self._lock = threading.Lock()

    # -- persistence ---------------------------------------------------

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        if not isinstance(data, list):
            return []
        # The file is hand-editable — drop malformed entries instead of
        # letting them crash retrieval/augmentation later.
        return [it for it in data if isinstance(it, dict)]

    def _write(self, items: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=str(self.path.parent), suffix=".tmp", prefix=self.path.name,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # -- CRUD ----------------------------------------------------------

    def list(self) -> list[dict[str, Any]]:
        return self._read()

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
        with self._lock:
            items = self._read()
            # Same question -> replace (latest confirmation wins), so a
            # re-verified pair never duplicates.
            items = [
                it for it in items
                if it.get("question", "").strip() != question
            ]
            entry = {
                "id": uuid.uuid4().hex[:12],
                "question": question,
                "sql": sql,
                "tables": list(tables or []),
                "source": source,
                "verified": bool(verified),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            items.append(entry)
            if len(items) > _MAX_EXAMPLES:
                items = items[-_MAX_EXAMPLES:]
            self._write(items)
            return entry

    def remove(self, example_id: str) -> bool:
        with self._lock:
            items = self._read()
            kept = [it for it in items if it.get("id") != example_id]
            if len(kept) == len(items):
                return False
            self._write(kept)
            return True

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

    def __len__(self) -> int:
        return len(self._read())

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
