"""Connection presets store — save/load database connection configs."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import tempfile
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover
    Fernet = None
    InvalidToken = Exception


_DEFAULT_PATH = Path.home() / ".seatunnel-agent" / "dc_connections.json"
_MAX_PRESETS = int(os.getenv("SEATUNNEL_DC_MAX_PRESETS", "50"))
_KEY_PATH = Path(os.getenv(
    "SEATUNNEL_DC_KEY_PATH",
    str(Path.home() / ".seatunnel-agent" / "dc_secret.key"),
))
_key_lock = threading.Lock()
_cached_key: bytes | None = None


def _load_or_create_key() -> bytes:
    """Return a 32-byte urlsafe-base64 key, creating the key file on first use."""
    global _cached_key
    with _key_lock:
        if _cached_key is not None:
            return _cached_key
        try:
            if _KEY_PATH.is_file():
                key = _KEY_PATH.read_bytes().strip()
                if key:
                    _cached_key = key
                    return key
        except OSError:
            pass
        key = base64.urlsafe_b64encode(secrets.token_bytes(32))
        _KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(_KEY_PATH), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, key)
        finally:
            os.close(fd)
        try:
            os.chmod(str(_KEY_PATH), 0o600)
        except OSError:  # pragma: no cover
            pass
        _cached_key = key
        return key


def _xor_keystream(data: bytes, key: bytes, nonce: bytes) -> bytes:
    """HMAC-SHA256 keystream XOR — fallback when cryptography is unavailable.

    Confidentiality only (no authentication); install `cryptography` for Fernet.
    """
    out = bytearray()
    counter = 0
    while len(out) < len(data):
        block = hmac.new(key, nonce + counter.to_bytes(4, "big"),
                         hashlib.sha256).digest()
        out.extend(block)
        counter += 1
    return bytes(b ^ k for b, k in zip(data, out))


def _encrypt(plaintext: str) -> str:
    if not plaintext:
        return ""
    key = _load_or_create_key()
    if Fernet is not None:
        return "enc1:" + Fernet(key).encrypt(plaintext.encode("utf-8")).decode("ascii")
    nonce = secrets.token_bytes(16)
    ct = _xor_keystream(plaintext.encode("utf-8"), key, nonce)
    return "obf1:" + base64.urlsafe_b64encode(nonce + ct).decode("ascii")


def _decrypt(stored: str) -> str:
    if not stored:
        return ""
    if stored.startswith("enc1:"):
        if Fernet is None:
            return ""
        try:
            key = _load_or_create_key()
            return Fernet(key).decrypt(stored[5:].encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError, OSError):
            return ""
    if stored.startswith("obf1:"):
        try:
            key = _load_or_create_key()
            raw = base64.urlsafe_b64decode(stored[5:])
            return _xor_keystream(raw[16:], key, raw[:16]).decode("utf-8")
        except (ValueError, OSError):
            return ""
    # Legacy formats: "b64:" obfuscation or bare plaintext.
    if stored.startswith("b64:"):
        try:
            return base64.b64decode(stored[4:]).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return ""
    return stored


def _is_legacy(stored: str) -> bool:
    return bool(stored) and not stored.startswith(("enc1:", "obf1:"))


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

    def _migrate_legacy(self, data: list[dict[str, Any]]) -> None:
        """Re-encrypt legacy (b64/plaintext) passwords in place and persist."""
        if not any(_is_legacy(d.get("password", "")) for d in data):
            return
        migrated = []
        for d in data:
            entry = dict(d)
            stored = entry.get("password", "")
            if _is_legacy(stored):
                entry["password"] = _encrypt(_decrypt(stored))
            migrated.append(entry)
        try:
            self._write(migrated)
        except OSError:
            pass

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            data = self._read()
            self._migrate_legacy(data)
            for d in data:
                d["password"] = _decrypt(d.get("password", ""))
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
            password=_encrypt(password),
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
            data = self._read()
            self._migrate_legacy(data)
            for d in data:
                if d.get("name") == name:
                    d["password"] = _decrypt(d.get("password", ""))
                    return d
        return None
