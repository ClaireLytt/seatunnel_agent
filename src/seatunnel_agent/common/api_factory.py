"""Factory for the standard agent API router pattern.

Most deterministic agent APIs share a shape: accept a directory path +
dialect + lang + report flag, call a pure domain function, and wrap the
result with ``report_to_dict`` / ``render_markdown``.  ``make_agent_router``
builds such a router in a few lines instead of copy-pasting the
boilerplate per agent.
"""

import time
from collections.abc import Callable, Sequence
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from seatunnel_agent.common.api_guard import add_health, check_path_allowed, ms_since
from seatunnel_agent.common.utils import normalize_lang


class _StandardResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


def make_agent_router(
    *,
    prefix: str,
    tags: Sequence[str],
    domain_fn: Callable[..., Any],
    request_model: type[BaseModel],
    allowed_dirs_env: str,
    health_name: str,
    report_to_dict: Callable[..., dict[str, Any]],
    render_markdown: Callable[..., str],
    path_field: str = "sql_dir",
    pre_check: Callable[..., None] | None = None,
) -> APIRouter:
    """Return a fully-wired :class:`APIRouter` for the common pattern.

    Parameters
    ----------
    prefix, tags:
        Passed straight to :class:`APIRouter`.
    domain_fn:
        ``domain_fn(path, dialect=dialect)`` — the pure analysis function.
    request_model:
        Pydantic model with at least *path_field*, ``dialect``, ``lang``,
        ``report`` fields.
    allowed_dirs_env:
        Env-var name for the directory whitelist.
    health_name:
        Label returned in the ``/health`` response.
    report_to_dict, render_markdown:
        Post-processing callables ``(domain_result, lang) -> …``.
    path_field:
        Name of the path attribute on *request_model* (default ``"sql_dir"``).
    pre_check:
        Optional ``pre_check(req)`` called before the domain function.
        Use it to validate extra request fields or set up context.
    """
    router = APIRouter(prefix=prefix, tags=list(tags))

    @router.post("/check", response_model=_StandardResponse)
    def check(req: request_model) -> _StandardResponse:  # type: ignore[valid-type]
        from pathlib import Path

        start = time.time()
        lang = normalize_lang(req.lang)  # type: ignore[attr-defined]
        raw_path: str = getattr(req, path_field)
        target = (raw_path or "").strip()
        check_path_allowed(target, allowed_dirs_env)
        if not Path(target).is_dir():
            raise HTTPException(
                status_code=400,
                detail={"code": "bad_dir", "path": target},
            )
        if pre_check is not None:
            pre_check(req)
        try:
            result = domain_fn(target, dialect=req.dialect)  # type: ignore[attr-defined]
        except Exception as exc:
            raise HTTPException(status_code=400, detail={
                "code": "check_failed",
                "error": f"{type(exc).__name__}: {exc}",
            })
        return _StandardResponse(
            result=report_to_dict(result, lang),
            report=render_markdown(result, lang) if req.report else None,  # type: ignore[attr-defined]
            elapsed_ms=ms_since(start),
        )

    add_health(router, health_name)
    return router
