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

from seatunnel_agent.common.api_guard import (
    add_health,
    ms_since,
    read_whitelisted_file,
    require_dir,
)
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
        start = time.time()
        lang = normalize_lang(req.lang)  # type: ignore[attr-defined]
        raw_path: str = getattr(req, path_field)
        target = require_dir(raw_path, allowed_dirs_env)
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


def make_text_router(
    *,
    prefix: str,
    tags: Sequence[str],
    endpoint: str,
    request_model: type[BaseModel],
    health_name: str,
    env_var: str,
    core: Callable[..., Any],
    render: Callable[..., str],
    to_payload: Callable[[Any], dict[str, Any]] | None = None,
    post: Callable[..., list[str]] | None = None,
    llm: Callable[..., tuple[str, Any, str]] | None = None,
) -> APIRouter:
    """Router for the text-input agent pipeline shared by most agents.

    The pipeline is fixed: resolve inputs → ``core`` (any failure is a
    400 with ``str(exc)``) → payload/report → optional ``post``
    sections → optional opt-in LLM section (failures are 503) →
    elapsed_ms + health.  Only the pieces that genuinely differ per
    agent are injected:

    core(req, resolve):
        The analysis.  ``resolve(file, text, what)`` reads a
        whitelisted file / falls back to inline text / raises the
        standard 400 when both are empty.  Raise ``HTTPException`` for
        bespoke 400s; any other exception becomes a 400.
    render(result, req, lang):
        The markdown report (only called when ``req.report``).
    to_payload(result):
        Defaults to ``result.to_dict()``.
    post(req, result, payload, lang):
        Optional extra sections — mutate *payload*, return the
        markdown fragments to append to the report.
    llm(req, result, lang):
        Called only when ``req.llm`` is true; returns
        ``(payload_key, value, markdown_section)``.  Any failure
        (missing key, provider error) is surfaced as a 503.
    """
    router = APIRouter(prefix=prefix, tags=list(tags))

    def resolve(file: str | None, text: str | None, what: str) -> str:
        if (file or "").strip():
            return read_whitelisted_file(file or "", env_var)
        if (text or "").strip():
            return text or ""
        raise HTTPException(status_code=400, detail=f"Provide {what}")

    def run(req) -> _StandardResponse:
        start = time.time()
        lang = normalize_lang(req.lang)
        try:
            result = core(req, resolve)
        except HTTPException:
            raise
        except Exception as exc:  # bad input, malformed JSON
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        payload = (to_payload(result) if to_payload is not None
                   else result.to_dict())
        report = (render(result, req, lang)
                  if req.report else None)
        if post is not None:
            for section in post(req, result, payload, lang):
                if report is not None:
                    report += "\n\n" + section
        if llm is not None and getattr(req, "llm", False):
            try:
                key, value, section = llm(req, result, lang)
            except HTTPException:
                raise
            except Exception as exc:  # missing key, provider errors
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            payload[key] = value
            if report is not None and section:
                report += "\n\n" + section
        return _StandardResponse(result=payload, report=report,
                                 elapsed_ms=ms_since(start))

    # FastAPI reads the request type from the annotation; binding it here
    # keeps the handler body free of per-model type suppressions.
    run.__annotations__["req"] = request_model
    router.post(f"/{endpoint}", response_model=_StandardResponse)(run)

    add_health(router, health_name)
    return router
