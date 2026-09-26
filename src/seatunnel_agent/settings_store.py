"""Runtime LLM settings — UI-editable overrides that replace editing .env.

The /settings page saves LLM credentials here instead of the local .env file.
Values live in ``~/.seatunnel-agent/llm_settings.json`` with the API key
encrypted at rest (same key file as the data-comparison presets store).
Overrides take effect by mutating ``os.environ`` — the same hook the CLI's
``--model/--provider`` flags use — so every code path that calls
``load_settings()`` per action picks them up immediately; pages that cache an
agent compare :func:`get_version` to invalidate.

Scope: the web UI process only.  CLI runs keep reading .env / flags.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

from .data_comparison.presets import _decrypt, _encrypt

# Env keys the /settings page manages; secrets are encrypted at rest.
MANAGED_KEYS = (
    "LLM_PROVIDER",
    "API_KEY",
    "MODEL_NAME",
    "LLM_BASE_URL",
    "TEMPERATURE",
    "MAX_TOKENS",
    "LLM_TIMEOUT",
)
SECRET_KEYS = ("API_KEY",)

_lock = threading.RLock()
_version = 0
# os.environ values (or absence) before the first apply — restored on clear().
_env_snapshot: dict[str, str | None] | None = None


def store_path() -> Path:
    """Settings file location (``SEATUNNEL_LLM_SETTINGS_PATH`` overrides)."""
    return Path(os.getenv(
        "SEATUNNEL_LLM_SETTINGS_PATH",
        str(Path.home() / ".seatunnel-agent" / "llm_settings.json"),
    ))


_MAX_PROFILES = 20


def _read_file() -> dict:
    """Raw file content normalized to the v2 schema {active, profiles}.

    v1 files were a flat {ENV_KEY: value} map — treated as the active set."""
    try:
        raw = json.loads(store_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"active": {}, "profiles": {}}
    if not isinstance(raw, dict):
        return {"active": {}, "profiles": {}}
    if "active" in raw or "profiles" in raw:
        active = raw.get("active") if isinstance(raw.get("active"), dict) else {}
        profiles = raw.get("profiles") if isinstance(raw.get("profiles"), dict) else {}
        return {"active": active, "profiles": profiles}
    return {"active": raw, "profiles": {}}  # legacy v1


def _write_file(data: dict) -> None:
    """Atomic write; the file is removed when nothing is stored at all."""
    path = store_path()
    if not data.get("active") and not data.get("profiles"):
        try:
            path.unlink()
        except OSError:
            pass
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _encode(values: dict[str, str]) -> dict[str, str]:
    """Managed keys only, blanks dropped, secrets encrypted."""
    out: dict[str, str] = {}
    for key in MANAGED_KEYS:
        val = (values.get(key) or "").strip()
        if not val:
            continue
        out[key] = _encrypt(val) if key in SECRET_KEYS else val
    return out


def _decode(stored: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    if not isinstance(stored, dict):
        return out
    for key in MANAGED_KEYS:
        val = stored.get(key)
        if not isinstance(val, str) or not val:
            continue
        plain = _decrypt(val) if key in SECRET_KEYS else val
        if plain:
            out[key] = plain
    return out


def load_saved() -> dict[str, str]:
    """Decrypted active overrides ({} when none); unknown/empty keys dropped."""
    return _decode(_read_file()["active"])


def has_saved() -> bool:
    return bool(load_saved())


def save(values: dict[str, str]) -> None:
    """Persist active overrides (managed keys only, blanks dropped) and apply."""
    with _lock:
        data = _read_file()
        data["active"] = _encode(values)
        _write_file(data)
        _apply_locked()


def clear() -> None:
    """Drop the active overrides (profiles are kept) and restore the env."""
    with _lock:
        data = _read_file()
        data["active"] = {}
        _write_file(data)
        _apply_locked()


# ── named profiles (e.g. one per provider: kimi / deepseek / claude) ──

def list_profiles() -> list[str]:
    return sorted(_read_file()["profiles"])


def load_profile(name: str) -> dict[str, str]:
    return _decode(_read_file()["profiles"].get(name, {}))


def save_profile(name: str, values: dict[str, str]) -> None:
    """Store a named snapshot (does NOT change the active overrides)."""
    name = (name or "").strip()
    if not name:
        raise ValueError("profile name is required")
    with _lock:
        data = _read_file()
        if name not in data["profiles"] and len(data["profiles"]) >= _MAX_PROFILES:
            raise ValueError(f"at most {_MAX_PROFILES} profiles")
        data["profiles"][name] = _encode(values)
        _write_file(data)


def activate_profile(name: str) -> None:
    """Copy a profile into the active overrides and apply it."""
    with _lock:
        data = _read_file()
        if name not in data["profiles"]:
            raise KeyError(name)
        data["active"] = dict(data["profiles"][name])
        _write_file(data)
        _apply_locked()


def delete_profile(name: str) -> None:
    with _lock:
        data = _read_file()
        data["profiles"].pop(name, None)
        _write_file(data)


def apply_to_env() -> None:
    """Push saved overrides into os.environ (call once at UI startup)."""
    with _lock:
        _apply_locked()


def _apply_locked() -> None:
    global _version, _env_snapshot
    if _env_snapshot is None:
        _env_snapshot = {k: os.environ.get(k) for k in MANAGED_KEYS}
    saved = load_saved()
    for key in MANAGED_KEYS:
        if key in saved:
            os.environ[key] = saved[key]
        else:
            # Not overridden (any more): restore what was there before the
            # first apply; a later load_dotenv() re-reads .env for gaps.
            orig = _env_snapshot.get(key)
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig
    _version += 1


def get_version() -> int:
    """Bumped on every save/clear/apply; agent caches compare it."""
    return _version


def mask_secret(value: str) -> str:
    """Display mask: ``sk-abcdefgh1234`` -> ``sk-***1234``.

    Keys shorter than 12 chars mask entirely — revealing 7 of, say, 9
    characters would be most of the secret."""
    if not value:
        return ""
    if len(value) < 12:
        return "***"
    return f"{value[:3]}***{value[-4:]}"
