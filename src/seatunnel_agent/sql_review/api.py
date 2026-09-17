"""REST API for the SQL Review agent — FastAPI router.

Mount on the Gradio app's FastAPI instance to serve alongside the UI.
Endpoints:
  POST /api/sql_review/review — review a SQL statement/script
  GET  /api/sql_review/health — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import load_settings
from ..text2sql.executor import DatabaseConfig, create_executor
from ..text2sql.schema import SchemaStore, parse_ddl
from .agent import SQLReviewAgent
from .linter import DIALECTS, is_known_dialect, normalize_dialect
from .rlog import ReviewLogger

router = APIRouter(prefix="/api/sql_review", tags=["sql_review"])


class ReviewRequest(BaseModel):
    sql: str = Field(..., min_length=1, description="SQL statement/script to review")
    dialect: str = Field("hive", description="hive | spark | flink | maxcompute")
    mode: str = Field("agent", description="'agent' (LLM review) or 'static' (linter only)")
    db_config: dict[str, Any] | None = Field(
        None, description="Optional connection for schema-aware review: host, port, database, username, password"
    )
    schema_ddl: str | None = Field(None, description="Optional inline DDL for table definitions")
    instructions: str | None = Field(None, description="Extra review instructions")


class ReviewResponse(BaseModel):
    report: str
    findings: list[dict[str, Any]]
    stats: dict[str, int]
    dialect: str
    elapsed_ms: int
    lineage: dict[str, Any] | None = None


def _build_store(
    dialect: str,
    db_config_dict: dict[str, Any] | None,
    schema_ddl: str | None,
) -> SchemaStore | None:
    store: SchemaStore | None = None
    if db_config_dict:
        try:
            db_config = DatabaseConfig(
                ds_type=dialect if dialect in ("hive", "spark", "flink") else "hive",
                host=db_config_dict.get("host", "localhost"),
                port=int(db_config_dict.get("port", 10000)),
                database=db_config_dict.get("database", "default"),
                username=db_config_dict.get("username"),
                password=db_config_dict.get("password"),
            )
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid db_config: {exc}")
        try:
            executor = create_executor(db_config)
            store = SchemaStore.from_db(executor)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Schema introspection failed: {exc}")
    if schema_ddl:
        tables = parse_ddl(schema_ddl)
        if store is not None:
            for t in tables:
                store.add(t)
        else:
            store = SchemaStore(tables)
    return store


@router.post("/review", response_model=ReviewResponse)
def review(req: ReviewRequest) -> ReviewResponse:
    start = time.time()
    if not is_known_dialect(req.dialect):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported dialect '{req.dialect}'. Valid: {', '.join(DIALECTS)}",
        )
    dialect = normalize_dialect(req.dialect)

    findings: list[dict[str, Any]] = []
    stats: dict[str, int] = {}
    lineage: dict[str, Any] | None = None

    store = _build_store(dialect, req.db_config, req.schema_ddl)

    if req.mode == "static":
        from .agent import static_review_report
        from .report import render_report
        rep = static_review_report(req.sql, dialect, store=store)
        report_md = render_report(rep)
        raw_findings = rep.findings
        findings = [f.to_dict() for f in raw_findings]
        stats = rep.stats()
        if rep.lineage:
            lineage = rep.lineage.to_dict()
    else:
        settings = load_settings()
        agent = SQLReviewAgent(settings, dialect=dialect, store=store)
        try:
            report_md = agent.review(req.sql, instructions=req.instructions or "")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Agent execution failed: {exc}")
        raw_findings = []
        if agent.runtime and agent.runtime.report:
            rep = agent.runtime.report
            raw_findings = rep.findings
            findings = [f.to_dict() for f in raw_findings]
            stats = rep.stats()
            if rep.lineage:
                lineage = rep.lineage.to_dict()

    elapsed_ms = int((time.time() - start) * 1000)
    ReviewLogger().log(
        sql=req.sql, dialect=dialect, mode=req.mode,
        findings=raw_findings, stats=stats, source="api", elapsed_ms=elapsed_ms,
    )

    return ReviewResponse(
        report=report_md,
        findings=findings,
        stats=stats,
        dialect=dialect,
        elapsed_ms=elapsed_ms,
        lineage=lineage,
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
