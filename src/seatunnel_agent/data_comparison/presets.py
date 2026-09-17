"""Connection presets store — save/load database connection configs."""

from __future__ import annotations

import base64
import json
import os
import tempfile
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_DEFAULT_PATH = Path.home() / ".seatunnel-agent" / "dc_connections.json"
_MAX_PRESETS = 50


def _obfuscate(plaintext: str) -> str:
    if not plaintext:
        return ""
    return "b64:" + base64.b64encode(plaintext.encode("utf-8")).decode("ascii")


def _deobfuscate(stored: str) -> str:
    if not stored:
        return ""
    if stored.startswith("b64:"):
        return base64.b64decode(stored[4:]).decode("utf-8")
    return stored


@dataclass
class ConnectionPreset:
    id: str
    name: str
    ds_type: str
    host: str
    port: int
    database: str
    username: str = ""
    password: str = ""
    environment: str = ""
    created_at: str = ""


class ConnectionPresetsStore:
    """Thread-safe JSON-backed connection presets storage."""

    def __init__(self, path: Path | str = _DEFAULT_PATH) -> None:
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
        fd, tmp = tempfile.mkstemp(
            dir=str(self.path.parent), suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, str(self.path))
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            data = self._read()
            for d in data:
                d["password"] = _deobfuscate(d.get("password", ""))
            return data

    def save(
        self,
        name: str,
        ds_type: str,
        host: str,
        port: int,
        database: str,
        username: str = "",
        password: str = "",
        environment: str = "",
    ) -> dict[str, Any]:
        if not name.strip():
            raise ValueError("Preset name must not be empty")
        preset = ConnectionPreset(
            id=uuid.uuid4().hex[:12],
            name=name.strip(),
            ds_type=ds_type,
            host=host,
            port=port,
            database=database,
            username=username,
            password=_obfuscate(password),
            environment=environment,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        entry = asdict(preset)
        with self._lock:
            data = self._read()
            data = [d for d in data if d.get("name") != name.strip()]
            data.insert(0, entry)
            if len(data) > _MAX_PRESETS:
                data = data[:_MAX_PRESETS]
            self._write(data)
        return entry

    def delete(self, preset_id: str) -> bool:
        with self._lock:
            data = self._read()
            before = len(data)
            data = [d for d in data if d.get("id") != preset_id]
            if len(data) < before:
                self._write(data)
                return True
        return False

    def get_by_name(self, name: str) -> dict[str, Any] | None:
        with self._lock:
            for d in self._read():
                if d.get("name") == name:
                    d["password"] = _deobfuscate(d.get("password", ""))
                    return d
        return None
