"""REST API for the SQL Review agent — FastAPI router.

Mount on the Gradio app's FastAPI instance to serve alongside the UI.
Endpoints:
  POST /api/sql_review/review — review a SQL statement/script
  POST /api/sql_review/fix    — LLM auto-fix based on a review report
  GET  /api/sql_review/health — health check
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import load_settings
from ..text2sql.executor import DatabaseConfig, create_executor
from ..text2sql.schema import SchemaStore, parse_ddl
from .agent import SQLReviewAgent
from .config import ReviewConfig, parse_config_data
from .i18n import normalize_lang
from .linter import DIALECTS, EXECUTOR_DS_TYPES, is_known_dialect, normalize_dialect
from .rlog import ReviewLogger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sql_review", tags=["sql_review"])

_DIALECT_DESC = " | ".join(DIALECTS)

# connection fallbacks when db_config omits them (overridable via env)
_DEFAULT_DB_HOST = os.getenv("SQLREVIEW_DB_HOST", "localhost")
_DEFAULT_DB_PORT = os.getenv("SQLREVIEW_DB_PORT", "10000")
_DEFAULT_DB_DATABASE = os.getenv("SQLREVIEW_DB_DATABASE", "default")


class ReviewRequest(BaseModel):
    sql: str = Field(..., min_length=1, description="SQL statement/script to review")
    dialect: str = Field("hive", description=_DIALECT_DESC)
    mode: str = Field("agent", description="'agent' (LLM review) or 'static' (linter only)")
    db_config: dict[str, Any] | None = Field(
        None, description="Optional connection for schema-aware review: host, port, database, username, password"
    )
    schema_ddl: str | None = Field(None, description="Optional inline DDL for table definitions")
    instructions: str | None = Field(None, description="Extra review instructions (agent mode only)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    rules: dict[str, Any] | None = Field(
        None, description="Inline rule config (same schema as .sqlreview.yaml)"
    )


class ReviewResponse(BaseModel):
    report: str
    findings: list[dict[str, Any]]
    stats: dict[str, int]
    dialect: str
    elapsed_ms: int
    lineage: dict[str, Any] | None = None
    warnings: list[str] = []


class FixRequest(BaseModel):
    sql: str = Field(..., min_length=1, description="SQL to fix")
    dialect: str = Field("hive", description=_DIALECT_DESC)
    report: str | None = Field(
        None, description="Review report markdown; when omitted a static review runs first"
    )
    lang: str = Field("zh", description="Comment language: 'zh' or 'en'")
    rules: dict[str, Any] | None = Field(
        None, description="Inline rule config used when the report must be generated"
    )


class FixResponse(BaseModel):
    fixed_sql: str
    report: str
    dialect: str
    elapsed_ms: int


def _parse_rules(rules: dict[str, Any] | None) -> ReviewConfig | None:
    if rules is None:
        return None
    try:
        return parse_config_data(rules)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid rules: {exc}")


def _build_store(
    dialect: str,
    db_config_dict: dict[str, Any] | None,
    schema_ddl: str | None,
    warnings: list[str],
) -> SchemaStore | None:
    store: SchemaStore | None = None
    if db_config_dict:
        ds_type = EXECUTOR_DS_TYPES.get(dialect)
        if ds_type is None:
            ds_type = "hive"
            msg = (
                f"dialect '{dialect}' has no dedicated executor; "
                "schema introspection falls back to the hive executor"
            )
            warnings.append(msg)
            logger.warning(msg)
        try:
            db_config = DatabaseConfig(
                ds_type=ds_type,
                host=db_config_dict.get("host", _DEFAULT_DB_HOST),
                port=int(db_config_dict.get("port", _DEFAULT_DB_PORT)),
                database=db_config_dict.get("database", _DEFAULT_DB_DATABASE),
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
    warnings: list[str] = []

    config = _parse_rules(req.rules)
    store = _build_store(dialect, req.db_config, req.schema_ddl, warnings)
    lang = normalize_lang(req.lang)

    if req.mode == "static":
        if req.instructions:
            warnings.append(
                "'instructions' only applies to agent mode and was ignored"
            )
        from .agent import static_review_report
        from .report import render_report
        rep = static_review_report(req.sql, dialect, store=store, config=config)
        report_md = render_report(rep, lang=lang)
        raw_findings = rep.findings
        findings = [f.to_dict() for f in raw_findings]
        stats = rep.stats()
        if rep.lineage:
            lineage = rep.lineage.to_dict()
    else:
        settings = load_settings()
        agent = SQLReviewAgent(
            settings, dialect=dialect, store=store, config=config, lang=lang
        )
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
        warnings=warnings,
    )


@router.post("/fix", response_model=FixResponse)
def fix(req: FixRequest) -> FixResponse:
    start = time.time()
    if not is_known_dialect(req.dialect):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported dialect '{req.dialect}'. Valid: {', '.join(DIALECTS)}",
        )
    dialect = normalize_dialect(req.dialect)
    lang = normalize_lang(req.lang)

    report_md = (req.report or "").strip()
    if not report_md:
        from .agent import static_review_report
        from .report import render_report
        config = _parse_rules(req.rules)
        rep = static_review_report(req.sql, dialect, config=config)
        report_md = render_report(rep, lang=lang)

    from .fixer import generate_fix
    settings = load_settings()
    try:
        fixed_sql = generate_fix(settings, req.sql, dialect, report_md, lang=lang)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Fix generation failed: {exc}")

    return FixResponse(
        fixed_sql=fixed_sql,
        report=report_md,
        dialect=dialect,
        elapsed_ms=int((time.time() - start) * 1000),
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
