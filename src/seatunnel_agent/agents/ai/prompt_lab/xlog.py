# -*- coding: utf-8 -*-
"""Experiment history for the prompt lab — JSONL, one line per matrix run.

Previews only (no full replies, never any API key).  Env knobs:
``PROMPT_LAB_LOG=0`` disables, ``PROMPT_LAB_PATH`` relocates the file.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from seatunnel_agent.common.jsonl_log import JsonlLog

if TYPE_CHECKING:  # pragma: no cover
    from .runner import MatrixResult

_PREVIEW_CHARS = 200


def log_path() -> Path:
    return Path(os.getenv("PROMPT_LAB_PATH") or "logs/prompt_lab.jsonl")


class ExperimentLogger:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else log_path()
        self._log = JsonlLog(lambda: self.path, env_switch="PROMPT_LAB_LOG")

    def log(self, result: "MatrixResult") -> None:
        """Best-effort append; never raises into the experiment."""
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
        except Exception:  # noqa: BLE001 — history is best-effort
            return
        self._log.append(rec)

    def recent(self, n: int = 20) -> list[dict[str, Any]]:
        return self._log.recent(n)
