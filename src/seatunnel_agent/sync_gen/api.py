# -*- coding: utf-8 -*-
"""REST API for the sync generator — FastAPI router.

Mount on the Gradio app's FastAPI instance (``seatunnel-agent ui --api``).
Offline only in v1 — the HTTP surface never touches DB credentials; live
introspection stays CLI-only. Nothing is written server-side: generated
file contents come back inline.

  POST /api/syncgen/generate — DDL → configs + target DDL + manifest
  GET  /api/syncgen/health   — health check
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..api_guard import check_path_allowed
from .core import SyncPlan, generate_sync
from .i18n import normalize_lang
from .report import render_markdown, report_to_dict

router = APIRouter(prefix="/api/syncgen", tags=["sync_gen"])


class SyncGenRequest(BaseModel):
    ddl_text: str | None = Field(None, description="Inline MySQL DDL script")
    ddl_path: str | None = Field(
        None, description="Server-side DDL file/dir (whitelisted dirs only)")
    sink_type: str = Field("console",
                           description="console | doris | starrocks | hive")
    include: str | None = Field(None, description="Table name include regex")
    exclude: str | None = Field(None, description="Table name exclude regex")
    pii: bool = Field(False, description="Inject masking transforms")
    pii_strategy: str = Field("md5", description="md5 | mask")
    parallelism: int = Field(2, ge=1, le=64)
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown")


class SyncGenResponse(BaseModel):
    manifest: dict[str, Any]
    files: dict[str, str]        # 相对路径 → 文件内容（内联，不落盘）
    report: str | None = None
    elapsed_ms: int


@router.post("/generate", response_model=SyncGenResponse)
def generate(req: SyncGenRequest) -> SyncGenResponse:
    start = time.time()
    lang = normalize_lang(req.lang)
    ddl_text = (req.ddl_text or "").strip() or None
    ddl_path = (req.ddl_path or "").strip() or None
    if not ddl_text and not ddl_path:
        raise HTTPException(status_code=400,
                            detail="需要 ddl_text 或 ddl_path")
    if ddl_path:
        # API 是网络入口，路径参数必须限制在白名单内，防任意文件读取。
        check_path_allowed(ddl_path, "SYNCGEN_API_ALLOWED_DIRS", noun="路径")
        if not Path(ddl_path).exists():
            raise HTTPException(status_code=400,
                                detail=f"路径不存在: {ddl_path}")
    plan = SyncPlan(
        source_mode="ddl", ddl_text=ddl_text, ddl_path=ddl_path,
        sink_type=req.sink_type, include=req.include, exclude=req.exclude,
        pii=req.pii, pii_strategy=req.pii_strategy,
        parallelism=req.parallelism)
    try:
        result = generate_sync(plan)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    files: dict[str, str] = {}
    for t in result.tables:
        files[f"configs/{t.file_stem}.conf"] = t.config_text
        if t.ddl_text:
            files[f"ddl/{t.file_stem}.sql"] = t.ddl_text
    rendered = render_markdown(result, lang=lang) if req.report else None
    return SyncGenResponse(
        manifest=report_to_dict(result, lang=lang),
        files=files,
        report=rendered,
        elapsed_ms=int((time.time() - start) * 1000))


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "sync_gen"}
