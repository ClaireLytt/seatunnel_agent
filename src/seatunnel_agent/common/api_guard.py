"""Shared directory whitelist for the REST APIs.

Every agent API that accepts a filesystem path is a network entry point, so
path parameters must stay inside a per-agent whitelist (an env var listing
allowed roots, defaulting to the current working directory). One
implementation here instead of a copy per agent module.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException


def allowed_roots(env_var: str) -> list[Path]:
    raw = os.getenv(env_var, "")
    roots = [Path(p).resolve() for p in raw.split(os.pathsep) if p.strip()]
    return roots or [Path.cwd().resolve()]


def check_path_allowed(raw_path: str, env_var: str, noun: str = "目录") -> None:
    """Raise 400/403 unless *raw_path* resolves under a whitelisted root."""
    try:
        target = Path(raw_path).resolve()
    except (OSError, ValueError):
        raise HTTPException(status_code=400, detail=f"无效{noun}: {raw_path}")
    if not any(
        target == root or target.is_relative_to(root)
        for root in allowed_roots(env_var)
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                f"{noun} {raw_path} 不在允许范围内。"
                f"默认仅允许当前工作目录，可通过环境变量 "
                f"{env_var} 配置（多个目录用系统路径分隔符分隔）"
            ),
        )


def require_dir(raw_path: str, env_var: str) -> str:
    """Whitelist-check *raw_path* and require it to be an existing
    directory — the shared head of every directory-taking API endpoint.
    Whitelist first (403, no existence probing), then a structured
    ``{"code": "bad_dir", "path"}`` 400 the React pages localize.
    Returns the stripped path."""
    path = (raw_path or "").strip()
    check_path_allowed(path, env_var)
    if not Path(path).is_dir():
        raise HTTPException(status_code=400,
                            detail={"code": "bad_dir", "path": path})
    return path


def read_whitelisted_file(raw_path: str, env_var: str) -> str:
    """Whitelist-check the file's parent dir, then read it (replace
    errors) — the shared head of every file-taking API endpoint."""
    path = Path((raw_path or "").strip())
    require_dir(str(path.parent), env_var)
    if not path.is_file():
        raise HTTPException(status_code=400, detail=f"Not a file: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def ms_since(start: float) -> int:
    """Elapsed milliseconds since a ``time.time()`` start stamp."""
    return int((time.time() - start) * 1000)


def add_health(router: APIRouter, agent: str) -> None:
    """Attach the standard ``GET /health`` endpoint to *router*."""
    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "agent": agent}


def resolve_file_or_text(file: str | None, text: str | None,
                         env_var: str) -> str:
    """The file-or-inline-text input shape shared by the agent routers:
    400 when neither is given, whitelisted read when a file is."""
    from fastapi import HTTPException

    if not (file or "").strip() and not (text or "").strip():
        raise HTTPException(status_code=400,
                            detail="Provide 'file' or 'text'")
    if (file or "").strip():
        return read_whitelisted_file(file or "", env_var)
    return text or ""
