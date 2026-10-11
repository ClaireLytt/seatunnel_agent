# -*- coding: utf-8 -*-
"""REST API for doc Q&A — FastAPI router.

  POST /api/docqa/ask   — retrieve (and optionally synthesize) an answer
  GET  /api/docqa/health — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from .answer import answer, normalize_lang
from .core import get_index

router = APIRouter(prefix="/api/docqa", tags=["doc_qa"])


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    k: int = Field(4, ge=1, le=10)
    llm: bool = Field(False, description="LLM synthesis (needs an API key)")
    lang: str = Field("zh", description="'zh' or 'en'")


class AskResponse(BaseModel):
    markdown: str
    hits: list[dict[str, Any]]
    elapsed_ms: int


@router.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    start = time.time()
    result = answer(req.question, get_index(), k=req.k,
                    lang=normalize_lang(req.lang), use_llm=req.llm)
    return AskResponse(
        markdown=result["markdown"], hits=result["hits"],
        elapsed_ms=int((time.time() - start) * 1000))


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "doc_qa"}
