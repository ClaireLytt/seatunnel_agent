"""SQL query favorites store — JSON file backend with parameter support."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from seatunnel_agent.common.json_file_store import JsonFileStore

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


_DEFAULT_FAVORITES_PATH = os.getenv(
    "SQL_FAVORITES_PATH", "config/sql_favorites.json"
)


class FavoritesStore(JsonFileStore):
    def __init__(self, path: str | Path | None = None) -> None:
        super().__init__(
            path if path is not None else _DEFAULT_FAVORITES_PATH,
            max_items=_MAX_FAVORITES,
        )

    def save(
        self,
        name: str,
        sql: str,
        question: str = "",
        ds_type: str = "",
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "id": self._make_id(),
            "name": name,
            "sql": sql,
            "question": question,
            "ds_type": ds_type,
            "params": extract_params(sql),
            "created_at": self._now_iso(),
        }
        return self._append(entry)

    def rename(self, fav_id: str, new_name: str) -> bool:
        return self._update_by_id(fav_id, name=new_name)

    def delete(self, fav_id: str) -> bool:
        return self._delete_by_id(fav_id)
