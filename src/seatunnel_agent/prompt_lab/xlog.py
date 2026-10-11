# -*- coding: utf-8 -*-
"""Experiment history for the prompt lab — JSONL, one line per matrix run.

Previews only (no full replies, never any API key).  Env knobs:
``PROMPT_LAB_LOG=0`` disables, ``PROMPT_LAB_PATH`` relocates the file.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from .runner import MatrixResult

_MAX_LOG_BYTES = 10 * 1024 * 1024
_PREVIEW_CHARS = 200


def log_path() -> Path:
    return Path(os.getenv("PROMPT_LAB_PATH") or "logs/prompt_lab.jsonl")


class ExperimentLogger:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else log_path()
        self._lock = threading.Lock()

    def log(self, result: "MatrixResult") -> None:
        """Best-effort append; never raises into the experiment."""
        if os.getenv("PROMPT_LAB_LOG", "1") == "0":
            return
        try:
            rec: dict[str, Any] = {
                "ts": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"),
                "prompt_preview": result.prompt[:_PREVIEW_CHARS],
                "system_preview": result.system[:_PREVIEW_CHARS],
                "cells": [{
                    "profile": c.profile,
                    "provider": c.provider,
                    "model": c.model,
                    "input_tokens": c.input_tokens,
                    "output_tokens": c.output_tokens,
                    "latency_ms": c.latency_ms,
                    "error": c.error,
                    "reply_preview": (c.reply or "")[:_PREVIEW_CHARS],
                } for c in result.cells],
            }
            line = json.dumps(rec, ensure_ascii=False)
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                if (self.path.is_file()
                        and self.path.stat().st_size > _MAX_LOG_BYTES):
                    lines = self.path.read_text(
                        encoding="utf-8").splitlines()
                    self.path.write_text(
                        "\n".join(lines[len(lines) // 2:]) + "\n",
                        encoding="utf-8")
                with self.path.open("a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
        except Exception:  # noqa: BLE001 — history is best-effort
            pass

    def recent(self, n: int = 20) -> list[dict[str, Any]]:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        out: list[dict[str, Any]] = []
        for line in lines[-n:]:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out
