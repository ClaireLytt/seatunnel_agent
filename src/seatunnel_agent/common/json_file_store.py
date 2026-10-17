"""Thread-safe JSON-file-backed list store with capacity cap.

Absorbs the boilerplate shared by FavoritesStore and ExampleStore:
locked reads/writes via ``read_json_list`` / ``write_json_atomic``,
list/delete-by-id/append-with-cap. Subclasses add only domain logic.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from seatunnel_agent.common.utils import read_json_list, write_json_atomic


class JsonFileStore:
    """Base class for JSON-file-backed list stores.

    Concrete stores subclass and add domain-specific write methods
    (``save``, ``add``, ``rename``, etc.) that call the protected
    helpers below.
    """

    def __init__(self, path: str | Path, *, max_items: int = 200) -> None:
        self.path = Path(path)
        self.max_items = max_items
        self._lock = threading.Lock()

    # -- persistence (protected) ----------------------------------------

    def _read(self) -> list[dict[str, Any]]:
        return read_json_list(self.path)

    def _write(self, data: list[dict[str, Any]]) -> None:
        write_json_atomic(self.path, data)

    # -- public read -----------------------------------------------------

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._read()

    def __len__(self) -> int:
        return len(self._read())

    # -- protected write helpers -----------------------------------------

    def _append(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Append *entry* under the lock, enforce max_items (FIFO)."""
        with self._lock:
            data = self._read()
            data.append(entry)
            if len(data) > self.max_items:
                data = data[-self.max_items:]
            self._write(data)
        return entry

    def _delete_by_id(self, item_id: str) -> bool:
        """Remove the first item whose ``id`` matches. Returns success."""
        with self._lock:
            data = self._read()
            before = len(data)
            data = [e for e in data if e.get("id") != item_id]
            if len(data) < before:
                self._write(data)
                return True
            return False

    def _update_by_id(self, item_id: str, **fields: Any) -> bool:
        """Merge *fields* into the item with the given id."""
        with self._lock:
            data = self._read()
            for entry in data:
                if entry.get("id") == item_id:
                    entry.update(fields)
                    self._write(data)
                    return True
            return False

    @staticmethod
    def _make_id() -> str:
        return uuid.uuid4().hex[:12]

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
