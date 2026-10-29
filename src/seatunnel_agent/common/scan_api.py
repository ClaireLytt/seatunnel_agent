"""Deep seam for the scan-shaped REST surface.

Three governance agents (pii_scan, lineage_hygiene, metadata_quality)
independently grew the same implicit interface: ``POST /scan`` taking
``{sql|dir, dialect, lang, report, ...}``, a directory whitelist, the
``{code, error}`` failure envelope, elapsed timing, an api-source history
record and the ``{result, report, elapsed_ms}`` response envelope. Two
adapters make a seam real — this module names the interface once and the
agents shrink to a :class:`ScanSpec` each.

The spec is the whole interface: everything a caller (or a new agent)
must know lives in its fields. Agent-specific endpoints (pii's ``/mask``
and ``/rules``) keep hanging off the returned router untouched.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, create_model

from seatunnel_agent.common.api_guard import add_health, ms_since, require_dir
from seatunnel_agent.common.utils import normalize_lang


class ScanRequest(BaseModel):
    """The shared request shape; specs may extend it via ``extra_fields``."""

    sql: str | None = Field(None, description="Inline SQL script")
    dir: str | None = Field(
        None, description="Directory scanned recursively for *.sql")
    dialect: str = Field("hive", description="SQL dialect for parsing")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(
        False, description="Include the rendered markdown report")


class ScanResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@dataclass(frozen=True)
class ScanSpec:
    """Everything an agent must declare to own a /scan endpoint."""

    name: str                       # health/agent id, e.g. "metadata_quality"
    prefix: str                     # router prefix, e.g. "/api/metaquality"
    whitelist_env: str              # env var holding the allowed directories
    error_code: str                 # failure envelope code, e.g. "scan_failed"
    # analyze entry points; ``extras`` are the spec's extra request fields
    analyze_dir: Callable[..., Any]     # (target, dialect=..., **extras)
    analyze_sql: Callable[..., Any]     # (sql, dialect=..., **extras)
    render: Callable[[Any, str], str]   # (result, lang) -> markdown
    to_dict: Callable[[Any, str], dict[str, Any]]  # (result, lang) -> payload
    log_run: Callable[[Any], None] | None = None   # api-source history hook
    # extra request fields: name -> (type, pydantic Field default)
    extra_fields: dict[str, tuple[type, Any]] = field(default_factory=dict)


def make_scan_router(spec: ScanSpec) -> APIRouter:
    """Build the standard ``POST /scan`` + ``GET /health`` router."""
    router = APIRouter(prefix=spec.prefix, tags=[spec.name])

    request_model: type[ScanRequest] = (
        create_model(  # type: ignore[call-overload]
            f"{spec.name}_ScanRequest", __base__=ScanRequest,
            **spec.extra_fields)
        if spec.extra_fields else ScanRequest)

    @router.post("/scan", response_model=ScanResponse)
    def scan(req: request_model) -> ScanResponse:  # type: ignore[valid-type]
        start = time.time()
        if not (req.sql or "").strip() and not (req.dir or "").strip():
            raise HTTPException(status_code=400,
                                detail="Provide 'sql' or 'dir'")
        lang = normalize_lang(req.lang)
        extras = {name: getattr(req, name) for name in spec.extra_fields}
        try:
            if (req.dir or "").strip():
                target = require_dir(req.dir or "", spec.whitelist_env)
                result = spec.analyze_dir(target, dialect=req.dialect,
                                          **extras)
            else:
                result = spec.analyze_sql(req.sql or "", dialect=req.dialect,
                                          **extras)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail={
                "code": spec.error_code,
                "error": f"{type(exc).__name__}: {exc}"})
        if spec.log_run is not None:
            spec.log_run(result)
        return ScanResponse(
            result=spec.to_dict(result, lang),
            report=spec.render(result, lang) if req.report else None,
            elapsed_ms=ms_since(start),
        )

    add_health(router, spec.name)
    return router
