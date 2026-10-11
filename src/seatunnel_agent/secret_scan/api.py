# -*- coding: utf-8 -*-
"""REST API for the secret scanner — FastAPI router.

Inline text only: the API is a network entry point and must not walk
arbitrary directories (directory scans are a CLI affair).

  POST /api/secretscan/scan — scan inline text
  GET  /api/secretscan/health — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from .report import normalize_lang, render_markdown
from .scanner import ScanResult, scan_text

router = APIRouter(prefix="/api/secretscan", tags=["secret_scan"])


class ScanRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text to scan")
    name: str = Field("<inline>", description="Label used in findings")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the markdown report")


class ScanResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/scan", response_model=ScanResponse)
def scan(req: ScanRequest) -> ScanResponse:
    start = time.time()
    result = ScanResult(findings=scan_text(req.text, req.name),
                        files_scanned=1)
    return ScanResponse(
        result=result.to_dict(),
        report=(render_markdown(result, normalize_lang(req.lang))
                if req.report else None),
        elapsed_ms=int((time.time() - start) * 1000),
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "secret_scan"}
