"""Shared append-only JSONL log with size-capped rotation and tail reads.

Single implementation behind the per-feature history/usage loggers
(llm_usage, prompt_lab, orchestrator chat, llm_eval runs, lineage queries):
best-effort append under a lock, 10 MB cap, and a tolerant ``recent()``
tail reader that skips malformed lines.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

MAX_LOG_BYTES = 10 * 1024 * 1024


class JsonlLog:
    """Append/tail a JSONL file; never raises out of ``append``.

    ``path`` may be a Path or a zero-arg callable (re-resolved on every
    use, so env-var relocation keeps working mid-process).
    ``env_switch``: name of an env var that disables appends when "0".
    ``rotate``: "halve" keeps the newest half in place; "rename" moves the
    full file aside to ``<stem>.1.jsonl`` and starts fresh.
    """

    def __init__(self, path: Path | str | Callable[[], Path], *,
                 env_switch: str | None = None,
                 max_bytes: int = MAX_LOG_BYTES,
                 rotate: str = "halve") -> None:
        self._path = path
        self.env_switch = env_switch
        self.max_bytes = max_bytes
        self.rotate = rotate
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        p = self._path
        return Path(p()) if callable(p) else Path(p)

    def append(self, rec: dict[str, Any]) -> None:
        """Best-effort append; must never raise into the caller."""
        if self.env_switch and os.getenv(self.env_switch, "1") == "0":
            return
        try:
            line = json.dumps(rec, ensure_ascii=False)
            path = self.path
            with self._lock:
                path.parent.mkdir(parents=True, exist_ok=True)
                self._rotate_if_needed(path)
                with path.open("a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
        except Exception:  # noqa: BLE001 — history/usage is best-effort
            pass

    def _rotate_if_needed(self, path: Path) -> None:
        if not (path.is_file() and path.stat().st_size > self.max_bytes):
            return
        if self.rotate == "rename":
            rotated = path.with_name(path.stem + ".1.jsonl")
            if rotated.exists():
                rotated.unlink()
            path.rename(rotated)
        else:  # halve
            lines = path.read_text(encoding="utf-8").splitlines()
            path.write_text("\n".join(lines[len(lines) // 2:]) + "\n",
                            encoding="utf-8")

    def recent(self, n: int = 20,
               where: Callable[[dict[str, Any]], bool] | None = None,
               ) -> list[dict[str, Any]]:
        """The last *n* parseable records (after optional filtering)."""
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        out: list[dict[str, Any]] = []
        for line in lines if where else lines[-n:]:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if where is None or where(rec):
                out.append(rec)
        return out[-n:]
