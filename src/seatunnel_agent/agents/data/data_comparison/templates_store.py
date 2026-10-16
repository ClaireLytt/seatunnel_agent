"""Comparison templates store — save/load full comparison configs."""

from __future__ import annotations

import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from seatunnel_agent.common.utils import read_json_list, write_json_atomic

_DEFAULT_PATH = Path.home() / ".seatunnel-agent" / "dc_templates.json"
_MAX_TEMPLATES = 100


@dataclass
class ComparisonTemplate:
    id: str
    name: str
    table_a: str
    table_b: str
    where_clause: str = ""
    key_columns: str = ""
    threshold: str = ""
    column_mapping: str = ""
    sample_strategy: str = "TOP N"
    watermark_column: str = ""
    quality_rules: str = ""
    webhook_url: str = ""
    notify_on_fail: bool = False
    masking_enabled: bool = True
    created_at: str = ""


class ComparisonTemplatesStore:
    """Thread-safe JSON-backed comparison templates storage."""

    def __init__(self, path: Path | str = _DEFAULT_PATH) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def _read(self) -> list[dict[str, Any]]:
        return read_json_list(self.path)

    def _write(self, data: list[dict[str, Any]]) -> None:
        write_json_atomic(self.path, data)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._read()

    def save(
        self,
        name: str,
        table_a: str,
        table_b: str,
        where_clause: str = "",
        key_columns: str = "",
        threshold: str = "",
        column_mapping: str = "",
        sample_strategy: str = "TOP N",
        watermark_column: str = "",
        quality_rules: str = "",
        webhook_url: str = "",
        notify_on_fail: bool = False,
        masking_enabled: bool = True,
    ) -> dict[str, Any]:
        if not name.strip():
            raise ValueError("Template name must not be empty")
        tmpl = ComparisonTemplate(
            id=uuid.uuid4().hex[:12],
            name=name.strip(),
            table_a=table_a,
            table_b=table_b,
            where_clause=where_clause,
            key_columns=key_columns,
            threshold=threshold,
            column_mapping=column_mapping,
            sample_strategy=sample_strategy,
            watermark_column=watermark_column,
            quality_rules=quality_rules,
            webhook_url=webhook_url,
            notify_on_fail=notify_on_fail,
            masking_enabled=masking_enabled,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        entry = asdict(tmpl)
        with self._lock:
            data = self._read()
            data = [d for d in data if d.get("name") != name.strip()]
            data.insert(0, entry)
            if len(data) > _MAX_TEMPLATES:
                data = data[:_MAX_TEMPLATES]
            self._write(data)
        return entry

    def delete(self, template_id: str) -> bool:
        with self._lock:
            data = self._read()
            before = len(data)
            data = [d for d in data if d.get("id") != template_id]
            if len(data) < before:
                self._write(data)
                return True
        return False

    def get_by_name(self, name: str) -> dict[str, Any] | None:
        with self._lock:
            for d in self._read():
                if d.get("name") == name:
                    return d
        return None
