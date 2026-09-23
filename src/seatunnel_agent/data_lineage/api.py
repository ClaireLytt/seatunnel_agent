"""REST API for the data lineage agent — FastAPI router.

Mount on the Gradio app's FastAPI instance to serve alongside the UI.
Endpoints:
  POST /api/lineage/query   — deterministic lineage query (no LLM)
  POST /api/lineage/analyze — natural-language question via the agent
  GET  /api/lineage/health  — health check
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import load_settings
from .agent import LineageAgent, static_lineage
from .config import DEFAULT_DEPTH, DIRECTIONS, MAX_DEPTH, load_lineage_config
from .loaders import build_graph
from .render import (
    render_health,
    render_path,
    render_path_mermaid,
    render_report,
    render_sla_impact,
)
from .rlog import LineageLogger

router = APIRouter(prefix="/api/lineage", tags=["lineage"])

_logger = LineageLogger()


class SourceRequest(BaseModel):
    sql_dir: str | None = Field(None, description="从该目录的 *.sql 文件构建血缘图")
    seatunnel_dir: str | None = Field(None, description="从该目录的 SeaTunnel 配置构建血缘图")
    use_hive: bool = Field(False, description="从 Hive 元数据血缘表构建")
    meta_table: str | None = Field(None, description="覆盖血缘元数据表名")
    partition: str | None = Field(None, description="覆盖 pt 分区（默认最新）")
    use_cache: bool = Field(True, description="使用 Hive 血缘图的本地 TTL 缓存")


class QueryRequest(SourceRequest):
    table: str = Field(..., min_length=1, description="目标表，如 zz.dwm_orders_df")
    direction: str = Field("both", description="upstream | downstream | both")
    depth: int = Field(DEFAULT_DEPTH, ge=1, le=MAX_DEPTH, description="遍历深度")
    column: str | None = Field(None, description="可选：字段级影响分析的字段名")


class QueryResponse(BaseModel):
    report: str
    mermaid: str
    nodes: dict[str, Any]
    edges: list[list[str]]
    stats: dict[str, Any]
    column_impact: dict[str, Any] | None = None
    warnings: list[str]
    elapsed_ms: int


class SnapshotRequest(SourceRequest):
    name: str = Field("", description="快照名（可选）")


class SnapshotDiffRequest(SourceRequest):
    snapshot: str = Field(..., min_length=1, description="快照名或文件名")


class PathRequest(SourceRequest):
    src: str = Field(..., min_length=1, description="起点表")
    dst: str = Field(..., min_length=1, description="终点表")


class SlaImpactRequest(SourceRequest):
    table: str = Field(..., min_length=1, description="延迟的表")
    delay_hours: float = Field(0.0, ge=0, description="假设延迟小时数")
    depth: int = Field(MAX_DEPTH, ge=1, le=MAX_DEPTH, description="遍历深度")


class AnalyzeRequest(SourceRequest):
    question: str = Field(..., min_length=1, description="自然语言血缘问题")


class AnalyzeResponse(BaseModel):
    answer: str
    mermaid: str
    stats: dict[str, Any]
    warnings: list[str]
    elapsed_ms: int


def _allowed_roots() -> list[Path]:
    raw = os.getenv("LINEAGE_API_ALLOWED_DIRS", "")
    roots = [
        Path(p).resolve() for p in raw.split(os.pathsep) if p.strip()
    ]
    return roots or [Path.cwd().resolve()]


def _check_dir_allowed(raw_dir: str) -> None:
    """API 是网络入口，目录参数必须限制在白名单内，防任意目录扫描。"""
    try:
        target = Path(raw_dir).resolve()
    except (OSError, ValueError):
        raise HTTPException(status_code=400, detail=f"无效目录: {raw_dir}")
    if not any(
        target == root or target.is_relative_to(root)
        for root in _allowed_roots()
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                f"目录 {raw_dir} 不在允许范围内。"
                "默认仅允许当前工作目录，可通过环境变量 "
                "LINEAGE_API_ALLOWED_DIRS 配置（多个目录用系统路径分隔符分隔）"
            ),
        )


def _build(req: QueryRequest | AnalyzeRequest | SourceRequest):
    if not req.sql_dir and not req.seatunnel_dir and not req.use_hive:
        raise HTTPException(
            status_code=400, detail="至少指定一个血缘来源：sql_dir / seatunnel_dir 或 use_hive"
        )
    if req.sql_dir:
        _check_dir_allowed(req.sql_dir)
    if req.seatunnel_dir:
        _check_dir_allowed(req.seatunnel_dir)
    try:
        return build_graph(
            sql_dir=req.sql_dir, use_hive=req.use_hive,
            meta_table=req.meta_table, partition=req.partition,
            seatunnel_dir=req.seatunnel_dir, use_cache=req.use_cache,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"血缘图构建失败: {exc}")


def _missing_404(graph, name: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "message": f"表 '{name}' 不在血缘图中",
            "suggestions": graph.suggest(name),
        },
    )


def _log_elapsed(
    start: float,
    graph_stats: dict[str, Any],
    *,
    query: str,
    mode: str,
    direction: str = "",
    chain_stats: dict[str, int] | None = None,
) -> int:
    elapsed_ms = int((time.time() - start) * 1000)
    _logger.log(
        query=query, direction=direction, mode=mode, source="api",
        graph_stats=graph_stats, chain_stats=chain_stats, elapsed_ms=elapsed_ms,
    )
    return elapsed_ms


@router.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    start = time.time()
    if req.direction not in DIRECTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"direction 必须是 {', '.join(DIRECTIONS)} 之一",
        )
    graph, warnings = _build(req)
    config = load_lineage_config()

    report = static_lineage(
        graph, req.table, req.direction, req.depth, column=req.column, config=config
    )
    chain = report.chain
    if chain and chain.missing_root:
        raise _missing_404(graph, req.table)

    graph_stats = graph.stats()
    elapsed_ms = _log_elapsed(
        start, graph_stats, query=req.table, direction=req.direction, mode="static",
        chain_stats={
            "upstream": chain.upstream_count if chain else 0,
            "downstream": chain.downstream_count if chain else 0,
        },
    )
    return QueryResponse(
        report=render_report(report),
        mermaid=report.mermaid,
        nodes={k: v.to_dict() for k, v in (chain.nodes if chain else {}).items()},
        edges=[list(e) for e in (chain.edges if chain else [])],
        stats={**report.stats(), "graph": graph_stats},
        column_impact=report.column_impact.to_dict() if report.column_impact else None,
        warnings=warnings,
        elapsed_ms=elapsed_ms,
    )


@router.post("/path")
def find_path(req: PathRequest) -> dict[str, Any]:
    start = time.time()
    graph, warnings = _build(req)
    for name in (req.src, req.dst):
        if graph.get(name) is None:
            raise _missing_404(graph, name)
    path = graph.path_between(req.src, req.dst)
    elapsed_ms = _log_elapsed(
        start, graph.stats(), query=f"{req.src}->{req.dst}", mode="path",
    )
    return {
        "found": path is not None,
        "path": path or [],
        "hops": len(path) - 1 if path else None,
        "markdown": render_path(path, req.src, req.dst, graph),
        "mermaid": render_path_mermaid(path, graph),
        "warnings": warnings,
        "elapsed_ms": elapsed_ms,
    }


@router.post("/sla_impact")
def sla_impact(req: SlaImpactRequest) -> dict[str, Any]:
    start = time.time()
    graph, warnings = _build(req)
    impact = graph.sla_impact(req.table, req.delay_hours, req.depth)
    if impact.missing_root:
        raise _missing_404(graph, req.table)
    elapsed_ms = _log_elapsed(start, graph.stats(), query=req.table, mode="sla")
    return {
        **impact.to_dict(),
        "markdown": render_sla_impact(impact),
        "warnings": warnings,
        "elapsed_ms": elapsed_ms,
    }


@router.post("/check")
def health_check(req: SourceRequest) -> dict[str, Any]:
    start = time.time()
    graph, warnings = _build(req)
    report = graph.health_check()
    elapsed_ms = _log_elapsed(start, graph.stats(), query="health_check", mode="health")
    return {
        **report.to_dict(),
        "markdown": render_health(report),
        "warnings": warnings,
        "elapsed_ms": elapsed_ms,
    }


@router.post("/snapshot")
def save_snapshot_endpoint(req: SnapshotRequest) -> dict[str, Any]:
    from .snapshot import save_snapshot

    start = time.time()
    graph, warnings = _build(req)
    try:
        path = save_snapshot(graph, name=req.name)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"快照保存失败: {exc}")
    graph_stats = graph.stats()
    elapsed_ms = _log_elapsed(
        start, graph_stats, query=req.name or path.name, mode="snapshot",
    )
    return {
        "file": path.name,
        "stats": graph_stats,
        "warnings": warnings,
        "elapsed_ms": elapsed_ms,
    }


@router.post("/snapshot_diff")
def snapshot_diff(req: SnapshotDiffRequest) -> dict[str, Any]:
    from .snapshot import diff_graphs, load_snapshot, render_diff_markdown

    start = time.time()
    graph, warnings = _build(req)
    old_graph = load_snapshot(req.snapshot)
    if old_graph is None:
        raise HTTPException(
            status_code=404, detail=f"找不到快照 '{req.snapshot}'"
        )
    diff = diff_graphs(old_graph, graph)
    elapsed_ms = _log_elapsed(
        start, graph.stats(), query=req.snapshot, mode="snapshot_diff",
    )
    return {
        **diff,
        "markdown": render_diff_markdown(diff),
        "warnings": warnings,
        "elapsed_ms": elapsed_ms,
    }


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    start = time.time()
    graph, warnings = _build(req)
    settings = load_settings()
    agent = LineageAgent(
        settings, graph=graph, sql_dir=req.sql_dir,
        seatunnel_dir=req.seatunnel_dir,
        hive_available=req.use_hive, meta_table=req.meta_table,
        partition=req.partition,
    )
    try:
        answer = agent.analyze(req.question)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {exc}")

    graph_stats = graph.stats()
    elapsed_ms = _log_elapsed(start, graph_stats, query=req.question, mode="agent")
    return AnalyzeResponse(
        answer=answer,
        mermaid=agent.runtime.last_mermaid,
        stats=graph_stats,
        warnings=warnings,
        elapsed_ms=elapsed_ms,
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
