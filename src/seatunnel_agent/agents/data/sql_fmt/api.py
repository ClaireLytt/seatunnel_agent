"""REST API for the SQL formatter — FastAPI router.

Mount on the Gradio app's FastAPI instance (``seatunnel-agent ui --api``).
Check-only — the API never writes to the filesystem (``--write`` is a CLI
affair). Directory checks are whitelist-guarded via SQLFMT_API_ALLOWED_DIRS.

  POST /api/sqlfmt/format — format inline SQL, or check a whitelisted directory
  GET  /api/sqlfmt/health — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import (
    add_health,
    check_path_allowed,
    ms_since,
    require_dir,
)
from seatunnel_agent.common.utils import normalize_lang

from .formatter import fmt_dir, format_text
from .report import render_batch_markdown, render_markdown, result_to_dict

router = APIRouter(prefix="/api/sqlfmt", tags=["sql_fmt"])


class FormatRequest(BaseModel):
    sql: str | None = Field(None, description="SQL script to format")
    dir: str | None = Field(
        None, description="Directory scanned recursively for *.sql (check-only)")
    dialect: str = Field("hive", description="SQL dialect for parsing")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


class FormatResponse(BaseModel):
    result: dict[str, Any] | None = None
    results: list[dict[str, Any]] | None = None
    report: str | None = None
    elapsed_ms: int


@router.post("/format", response_model=FormatResponse)
def format_sql(req: FormatRequest) -> FormatResponse:
    start = time.time()
    if not (req.sql or "").strip() and not (req.dir or "").strip():
        raise HTTPException(status_code=400, detail="Provide 'sql' or 'dir'")
    lang = normalize_lang(req.lang)
    if (req.dir or "").strip():
        from pathlib import Path

        # whitelist first (403 for out-of-scope paths — no existence probing),
        # then a structured detail the frontend localizes (i18n `bad_dir`)
        check_path_allowed(req.dir.strip(), "SQLFMT_API_ALLOWED_DIRS")
        if not Path(req.dir.strip()).is_dir():
            raise HTTPException(status_code=400,
                                detail={"code": "bad_dir", "path": req.dir})
        target = require_dir(req.dir, "SQLFMT_API_ALLOWED_DIRS")
        results = fmt_dir(target, dialect=req.dialect, write=False)
        return FormatResponse(
            results=[r.to_dict() for r in results],
            report=render_batch_markdown(results, lang) if req.report else None,
            elapsed_ms=ms_since(start),
        )
    result = format_text(req.sql, dialect=req.dialect)
    return FormatResponse(
        result=result_to_dict(result),
        report=render_markdown(result, lang) if req.report else None,
        elapsed_ms=ms_since(start),
    )


add_health(router, "sql_fmt")
