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


def load_saved() -> dict[str, str]:
    """Decrypted saved overrides ({} when none); unknown/empty keys dropped."""
    try:
        raw = json.loads(store_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key in MANAGED_KEYS:
        val = raw.get(key)
        if not isinstance(val, str) or not val:
            continue
        plain = _decrypt(val) if key in SECRET_KEYS else val
        if plain:
            out[key] = plain
    return out


def has_saved() -> bool:
    return bool(load_saved())


def save(values: dict[str, str]) -> None:
    """Persist overrides (managed keys only, blanks dropped) and apply them."""
    with _lock:
        data: dict[str, str] = {}
        for key in MANAGED_KEYS:
            val = (values.get(key) or "").strip()
            if not val:
                continue
            data[key] = _encrypt(val) if key in SECRET_KEYS else val
        path = store_path()
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
        _apply_locked()


def clear() -> None:
    """Delete saved overrides and restore the pre-apply environment."""
    with _lock:
        try:
            store_path().unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass
        _apply_locked()


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
    """Display mask: ``sk-abcdefg1234`` -> ``sk-***1234``; short keys -> ***."""
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:3]}***{value[-4:]}"
