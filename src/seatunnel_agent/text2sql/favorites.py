"""SQL query favorites store — JSON file backend with parameter support."""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_MAX_FAVORITES = 200
_PARAM_RE = re.compile(r"\$\{(\w+)\}")


def extract_params(sql: str) -> list[str]:
    """Extract unique ``${param}`` placeholder names from SQL, in order."""
    seen: set[str] = set()
    params: list[str] = []
    for m in _PARAM_RE.finditer(sql):
        name = m.group(1)
        if name not in seen:
            seen.add(name)
            params.append(name)
    return params


def apply_params(sql: str, values: dict[str, str]) -> str:
    """Replace ``${param}`` placeholders with provided values.

    **Security note**: values are interpolated as-is (no escaping). This is
    intentional for template parameter substitution in the UI, but callers
    must never pass unsanitised end-user input as *values* if the resulting
    SQL will be executed directly.

    Raises ``ValueError`` if a placeholder has no corresponding value.
    """
    def _replace(m: re.Match) -> str:
        name = m.group(1)
        if name not in values:
            raise ValueError(f"Missing value for parameter: ${{{name}}}")
        return values[name]
    return _PARAM_RE.sub(_replace, sql)


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
        content = json.dumps(data, ensure_ascii=False, indent=2)
        fd, tmp = tempfile.mkstemp(
            dir=str(self.path.parent), suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp, str(self.path))
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

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
            "params": extract_params(sql),
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        with self._lock:
            data = self._read()
            data.append(entry)
            if len(data) > _MAX_FAVORITES:
                data = data[-_MAX_FAVORITES:]
            self._write(data)
        return entry

    def rename(self, fav_id: str, new_name: str) -> bool:
        with self._lock:
            data = self._read()
            for entry in data:
                if entry.get("id") == fav_id:
                    entry["name"] = new_name
                    self._write(data)
                    return True
            return False

    def delete(self, fav_id: str) -> bool:
        with self._lock:
            data = self._read()
            before = len(data)
            data = [e for e in data if e.get("id") != fav_id]
            if len(data) < before:
                self._write(data)
                return True
            return False
