# -*- coding: utf-8 -*-
"""Shared directory whitelist for the REST APIs.

Every agent API that accepts a filesystem path is a network entry point, so
path parameters must stay inside a per-agent whitelist (an env var listing
allowed roots, defaulting to the current working directory). One
implementation here instead of a copy per agent module.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import HTTPException


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
