"""SQL query favorites store — JSON file backend."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


class FavoritesStore:
    def __init__(self, path: str | Path = "config/sql_favorites.json") -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def _write(self, data: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._read()

    def save(
        self,
        name: str,
        sql: str,
        question: str = "",
        ds_type: str = "",
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "id": uuid.uuid4().hex[:12],
            "name": name,
            "sql": sql,
            "question": question,
            "ds_type": ds_type,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        with self._lock:
            data = self._read()
            data.append(entry)
            self._write(data)
        return entry

    def delete(self, fav_id: str) -> bool:
        with self._lock:
            data = self._read()
            before = len(data)
            data = [e for e in data if e.get("id") != fav_id]
            if len(data) < before:
                self._write(data)
                return True
            return False
