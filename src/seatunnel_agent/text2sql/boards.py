"""Pinned-query boards (轻量看板) — not a drag-and-drop report designer.

A board is an ordered list of pinned queries: each item snapshots the SQL
(and its question as the title) at pin time. Rendering a board re-executes
every item through the same validator / whitelist / LIMIT stack as
interactive queries and lets the existing chart machinery draw each result.
Storage style/limits mirror ``favorites.py``: one JSON file, atomic
replace, bounded size.
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

_MAX_BOARDS = 50
_MAX_ITEMS = 30

_DEFAULT_BOARDS_PATH = os.getenv("T2S_BOARDS_PATH", "config/t2s_boards.json")


class BoardStore:
    """JSON-file-backed store of boards of pinned queries."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path if path is not None else _DEFAULT_BOARDS_PATH)
        self._lock = threading.Lock()

    # -- persistence ---------------------------------------------------

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        return data if isinstance(data, list) else []

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

    # -- boards ----------------------------------------------------------

    def list(self) -> list[dict[str, Any]]:
        return self._read()

    def get(self, board_id: str) -> dict[str, Any] | None:
        for b in self._read():
            if b.get("id") == board_id:
                return b
        return None

    def get_by_name(self, name: str) -> dict[str, Any] | None:
        name = name.strip()
        for b in self._read():
            if b.get("name", "").strip() == name:
                return b
        return None

    def create(self, name: str) -> dict[str, Any]:
        name = name.strip()
        if not name:
            raise ValueError("看板名称不能为空")
        with self._lock:
            boards = self._read()
            if any(b.get("name", "").strip() == name for b in boards):
                raise ValueError(f"看板 '{name}' 已存在")
            if len(boards) >= _MAX_BOARDS:
                raise ValueError(f"看板数量已达上限 {_MAX_BOARDS}")
            board = {
                "id": uuid.uuid4().hex[:12],
                "name": name,
                "items": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            boards.append(board)
            self._write(boards)
            return board

    def delete(self, board_id: str) -> bool:
        with self._lock:
            boards = self._read()
            kept = [b for b in boards if b.get("id") != board_id]
            if len(kept) == len(boards):
                return False
            self._write(kept)
            return True

    # -- items -----------------------------------------------------------

    def pin(
        self, board_id: str, title: str, sql: str, ds_type: str = "",
    ) -> dict[str, Any]:
        title = title.strip() or sql.strip()[:40]
        sql = sql.strip()
        if not sql:
            raise ValueError("没有可钉选的 SQL")
        with self._lock:
            boards = self._read()
            for b in boards:
                if b.get("id") != board_id:
                    continue
                items = b.setdefault("items", [])
                if len(items) >= _MAX_ITEMS:
                    raise ValueError(f"该看板项目已达上限 {_MAX_ITEMS}")
                item = {
                    "id": uuid.uuid4().hex[:12],
                    "title": title[:100],
                    "sql": sql,
                    "ds_type": ds_type,
                    "pinned_at": datetime.now(timezone.utc).isoformat(),
                }
                items.append(item)
                self._write(boards)
                return item
        raise ValueError(f"看板 '{board_id}' 不存在")

    def unpin(self, board_id: str, item_id: str) -> bool:
        with self._lock:
            boards = self._read()
            for b in boards:
                if b.get("id") != board_id:
                    continue
                items = b.get("items", [])
                kept = [it for it in items if it.get("id") != item_id]
                if len(kept) == len(items):
                    return False
                b["items"] = kept
                self._write(boards)
                return True
            return False


def render_board(
    board: dict[str, Any],
    executor,
    schema_store,
    ds_type: str = "hive",
    default_limit: int = 1000,
    max_preview_rows: int = 10,
) -> list[dict[str, Any]]:
    """Execute every item and return per-item results (never raises; each
    item carries its own error). The caller renders tables/charts."""
    from .validator import enforce_limit, validate_sql

    out: list[dict[str, Any]] = []
    for item in board.get("items", []):
        sql = item.get("sql", "")
        entry: dict[str, Any] = {
            "id": item.get("id", ""),
            "title": item.get("title", ""),
            "sql": sql,
        }
        validation = validate_sql(sql, schema_store)
        if not validation.ok:
            entry["error"] = "SQL rejected: " + "; ".join(validation.errors)
            out.append(entry)
            continue
        final_sql = enforce_limit(sql, default_limit=default_limit, dialect=ds_type)
        try:
            result = executor.run(final_sql, max_rows=default_limit)
        except Exception as exc:
            entry["error"] = str(exc)
            out.append(entry)
            continue
        from .masking import apply_masking

        preview, _masked = apply_masking(
            result.columns, result.rows[:max_preview_rows],
        )
        entry.update({
            "columns": result.columns,
            "rows": [list(r) for r in preview],
            "row_count": result.row_count,
            "elapsed_ms": result.elapsed_ms,
        })
        out.append(entry)
    return out
