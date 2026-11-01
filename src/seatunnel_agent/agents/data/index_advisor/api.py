"""REST API for the index advisor — FastAPI router.

  POST /api/indexadvisor/recommend — per-table partition/bucket/index picks
  GET  /api/indexadvisor/health    — health check
"""

from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router
from seatunnel_agent.common.api_guard import (
    read_whitelisted_file,
    require_dir,
)
from seatunnel_agent.common.utils import collect_sql_files

from .advisor import analyze_workload, audit, cold_columns, recommend
from .report import render_audit, render_cold_columns, render_markdown

_ENV = "INDEXADVISOR_API_ALLOWED_DIRS"


class RecommendRequest(BaseModel):
    sql_dir: str | None = Field(
        None, description="Workload directory (recursive *.sql)")
    text: str | None = Field(None, description="Inline multi-statement SQL")
    ddl: str = Field("", description="Optional CREATE TABLE DDL text")
    dialect: str = Field("hive", description="SQL dialect for parsing")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _workload(req: RecommendRequest) -> str:
    if (req.sql_dir or "").strip():
        sql_dir = require_dir(req.sql_dir or "", _ENV)
        return "\n;\n".join(
            read_whitelisted_file(str(p), _ENV)
            for p in collect_sql_files(sql_dir))
    if (req.text or "").strip():
        return req.text or ""
    raise HTTPException(status_code=400, detail="Provide 'sql_dir' or 'text'")


def _core(req: RecommendRequest, resolve):
    workload = _workload(req)
    advice = recommend(analyze_workload(workload, dialect=req.dialect),
                       ddl_text=req.ddl)
    return workload, advice


def _post(req: RecommendRequest, result, payload, lang: str) -> list[str]:
    workload, advice = result
    if not req.ddl.strip():
        return []
    sections = []
    findings = audit(advice, req.ddl)
    payload["audit"] = findings
    sections.append(render_audit(findings, lang=lang))
    cold = cold_columns(advice, req.ddl, workload)
    if cold:
        payload["cold_columns"] = cold
        sections.append(render_cold_columns(cold, lang=lang))
    return sections


router = make_text_router(
    prefix="/api/indexadvisor", tags=["index_advisor"],
    endpoint="recommend", request_model=RecommendRequest,
    health_name="index_advisor", env_var=_ENV,
    core=_core,
    to_payload=lambda result: result[1].to_dict(),
    render=lambda result, req, lang: render_markdown(result[1], lang=lang),
    post=_post,
)
