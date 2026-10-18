"""REST API for the data lineage agent — FastAPI router.

Mount on the Gradio app's FastAPI instance to serve alongside the UI.
Endpoints:
  POST /api/lineage/query   — deterministic lineage query (no LLM)
  POST /api/lineage/analyze — natural-language question via the agent
  GET  /api/lineage/health  — health check

plus the session surface the React page uses (build once, query many):
POST /session, POST /build, POST /search, GET /snapshots, and SSE
POST /analyze/stream. Every source-taking request also accepts an
optional ``session_id`` — when set, the session's already-built graph is
reused instead of rebuilding from the source params.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import ms_since
from seatunnel_agent.common.config import load_settings

from .agent import LineageAgent, static_lineage
from .config import DEFAULT_DEPTH, DIRECTIONS, MAX_DEPTH, load_lineage_config
from .loaders import build_graph
from .render import (
    render_health,
    render_mermaid,
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
    sql_dialect: str = Field("hive", description="解析 sql_dir 脚本用的 SQL 方言")
    seatunnel_dir: str | None = Field(None, description="从该目录的 SeaTunnel 配置构建血缘图")
    use_hive: bool = Field(False, description="从 Hive 元数据血缘表构建")
    meta_table: str | None = Field(None, description="覆盖血缘元数据表名")
    partition: str | None = Field(None, description="覆盖 pt 分区（默认最新）")
    use_cache: bool = Field(True, description="使用 Hive 血缘图的本地 TTL 缓存")
    session_id: str = Field(
        "", description="可选：复用该会话里已构建的血缘图（POST /build）")


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


def _check_dir_allowed(raw_dir: str) -> None:
    """API 是网络入口，目录参数必须限制在白名单内，防任意目录扫描。"""
    from seatunnel_agent.common.api_guard import check_path_allowed

    check_path_allowed(raw_dir, "LINEAGE_API_ALLOWED_DIRS")


def _build(req: QueryRequest | AnalyzeRequest | SourceRequest):
    if not req.sql_dir and not req.seatunnel_dir and not req.use_hive:
        raise HTTPException(status_code=400, detail={
            "code": "need_source",
            "message": "至少指定一个血缘来源：sql_dir / seatunnel_dir 或 use_hive"})
    if req.sql_dir:
        _check_dir_allowed(req.sql_dir)
    if req.seatunnel_dir:
        _check_dir_allowed(req.seatunnel_dir)
    try:
        return build_graph(
            sql_dir=req.sql_dir, use_hive=req.use_hive,
            meta_table=req.meta_table, partition=req.partition,
            seatunnel_dir=req.seatunnel_dir, use_cache=req.use_cache,
            sql_dialect=req.sql_dialect,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail={
            "code": "build_failed", "message": f"血缘图构建失败: {exc}"})


def _graph_for(req: SourceRequest):
    """The session's built graph when ``session_id`` is set (structured
    need_graph error if none built yet), else a fresh legacy build."""
    if req.session_id:
        from .registry import get_registry

        session = get_registry().get(req.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="unknown session_id")
        if not session.built:
            raise HTTPException(status_code=400,
                                detail={"code": "need_graph"})
        return session.graph, list(session.warnings)
    return _build(req)


def _missing_404(graph, name: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "code": "not_found",
            "table": name,
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
    elapsed_ms = ms_since(start)
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
    graph, warnings = _graph_for(req)
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
    graph, warnings = _graph_for(req)
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
    graph, warnings = _graph_for(req)
    config = load_lineage_config()
    # report and chain mermaid share one BFS (legacy UI do_sla parity)
    chain = graph.downstream_of(req.table, req.depth, config.max_nodes)
    impact = graph.sla_impact(req.table, req.delay_hours, depth=req.depth,
                              max_nodes=config.max_nodes, chain=chain)
    if impact.missing_root:
        raise _missing_404(graph, req.table)
    elapsed_ms = _log_elapsed(start, graph.stats(), query=req.table, mode="sla")
    return {
        **impact.to_dict(),
        "markdown": render_sla_impact(impact),
        "mermaid": render_mermaid(chain, config.max_mermaid_nodes),
        "warnings": warnings,
        "elapsed_ms": elapsed_ms,
    }


@router.post("/check")
def health_check(req: SourceRequest) -> dict[str, Any]:
    start = time.time()
    graph, warnings = _graph_for(req)
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
    graph, warnings = _graph_for(req)
    try:
        path = save_snapshot(graph, name=req.name)
    except OSError as exc:
        raise HTTPException(status_code=400, detail={
            "code": "snap_save_failed", "message": f"快照保存失败: {exc}"})
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
    graph, warnings = _graph_for(req)
    old_graph = load_snapshot(req.snapshot)
    if old_graph is None:
        raise HTTPException(status_code=404, detail={
            "code": "snap_not_found",
            "message": f"找不到快照 '{req.snapshot}'"})
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
    graph, warnings = _graph_for(req)
    settings = load_settings()
    agent = LineageAgent(
        settings, graph=graph, sql_dir=req.sql_dir,
        sql_dialect=req.sql_dialect,
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


class ImpactRequest(BaseModel):
    old_dir: str | None = Field(None, description="旧 SQL 目录（目录模式）")
    new_dir: str | None = Field(None, description="新 SQL 目录（目录模式）")
    old_sql: str | None = Field(None, description="旧 SQL 文本（粘贴模式）")
    new_sql: str | None = Field(None, description="新 SQL 文本（粘贴模式）")
    context_dir: str | None = Field(
        None, description="粘贴模式可选：仓库 SQL 目录，下游波及按全仓血缘计算")
    depth: int = Field(3, ge=1, le=MAX_DEPTH, description="下游遍历深度")
    sql_dialect: str = Field("hive", description="解析 SQL 用的方言")
    lang: str = Field("zh", description="报告语言 zh|en")


@router.post("/impact")
def change_impact(req: ImpactRequest) -> dict[str, Any]:
    """变更影响分析：两份 SQL 目录（或两段粘贴 SQL）的血缘 diff + 下游波及。
    纯确定性。目录模式与文本模式二选一。"""
    from .impact import analyze_dirs, analyze_sql_texts, impact_to_dict

    dir_mode = bool(req.old_dir and req.new_dir)
    text_mode = bool(req.old_sql and req.new_sql)
    if dir_mode == text_mode:
        raise HTTPException(
            status_code=400,
            detail="请二选一：old_dir+new_dir（目录模式）或 old_sql+new_sql（文本模式）",
        )
    from pathlib import Path

    def _require_dir(d: str) -> None:
        # whitelist first (403, no existence probing), then a structured
        # detail the frontend localizes (i18n `bad_dir`)
        _check_dir_allowed(d)
        if not Path(d).is_dir():
            raise HTTPException(status_code=400,
                                detail={"code": "bad_dir", "path": d})

    start = time.time()
    try:
        if dir_mode:
            _require_dir(req.old_dir)
            _require_dir(req.new_dir)
            result = analyze_dirs(req.old_dir, req.new_dir, depth=req.depth,
                                  sql_dialect=req.sql_dialect)
        else:
            if req.context_dir:
                _require_dir(req.context_dir)
            result = analyze_sql_texts(req.old_sql, req.new_sql,
                                       depth=req.depth,
                                       sql_dialect=req.sql_dialect,
                                       context_dir=req.context_dir)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400,
                            detail=f"变更影响分析失败: {exc}")
    data = impact_to_dict(result, req.lang)
    # additive fields for the React page: severity-coloured graph source
    # (always) and the unified SQL diff (paste mode, legacy do_analyze_sql)
    from .impact import render_impact_mermaid, render_text_diff

    data["mermaid"] = render_impact_mermaid(result)
    if text_mode:
        data["sql_diff"] = render_text_diff(req.old_sql, req.new_sql)
    data["elapsed_ms"] = ms_since(start)
    from .impact import ImpactLogger
    ImpactLogger().log_impact(
        result, mode="dirs" if dir_mode else "text", source="api",
        baseline=req.old_dir or "<inline>")
    return data


# ──────────────────── React-page session surface ────────────────────


@router.post("/session")
def create_session() -> dict[str, str]:
    """Issue a new per-tab session in the lineage graph registry."""
    from .registry import get_registry

    return {"session_id": get_registry().create().session_id}


@router.post("/build")
def build(req: SourceRequest) -> dict[str, Any]:
    """Build the lineage graph once and park it in the session (the Gradio
    page's gr.State equivalent). Returns stats + the table list that fills
    the query dropdowns."""
    if not req.session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    from .registry import get_registry

    session = get_registry().get(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown session_id")
    graph, warnings = _build(req)
    with session.lock:
        session.graph = graph
        session.warnings = list(warnings)
    stats = graph.stats()
    return {"stats": stats, "tables": sorted(graph.nodes),
            "warnings": warnings}


class SearchRequest(SourceRequest):
    keyword: str = Field(..., min_length=1, description="表名模糊搜索关键词")
    limit: int = Field(20, ge=1, le=100)


@router.post("/search")
def search(req: SearchRequest) -> dict[str, Any]:
    """Fuzzy table-name search over the built graph (legacy do_search)."""
    graph, _ = _graph_for(req)
    return {"matches": [
        {"name": n.name, "layer": getattr(n, "layer", "") or ""}
        for n in graph.search(req.keyword, req.limit)]}


@router.get("/snapshots")
def snapshots() -> dict[str, Any]:
    """Saved snapshots for the diff dropdown (legacy _snapshot_choices)."""
    from .snapshot import list_snapshots

    return {"snapshots": list_snapshots()}


def _sse(data: dict[str, Any]) -> str:
    import json

    return "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"


@router.post("/analyze/stream")
def analyze_stream(req: AnalyzeRequest):
    """SSE variant of /analyze streaming agent progress (legacy do_ask).

    Frames: step {iteration, max, phase}, tool {name, input}, delta
    {text}, final {answer, mermaid [, error]}. The blocking /analyze
    endpoint is unchanged; "no_settings" comes back as a structured final
    frame, never a 500.
    """
    import threading

    from fastapi.responses import StreamingResponse

    from seatunnel_agent.agents.data.seatunnel.rendering import EventCollector

    graph, _warnings = _graph_for(req)
    try:
        settings = load_settings()
    except Exception:
        def no_settings_stream():
            yield _sse({"type": "final", "answer": "",
                        "mermaid": "", "error": "no_settings"})

        return StreamingResponse(no_settings_stream(),
                                 media_type="text/event-stream")

    collector = EventCollector()
    done = threading.Event()
    result: dict[str, Any] = {}

    def worker() -> None:
        try:
            agent = LineageAgent(
                settings, graph=graph,
                sql_dir=(req.sql_dir or "").strip() or None,
                sql_dialect=req.sql_dialect,
                seatunnel_dir=(req.seatunnel_dir or "").strip() or None,
                hive_available=req.use_hive,
                meta_table=(req.meta_table or "").strip() or None,
                partition=(req.partition or "").strip() or None,
                on_event=collector.on_event,
            )
            result["answer"] = agent.analyze(req.question)
            result["mermaid"] = agent.runtime.last_mermaid
        except Exception as exc:  # structured final frame, generic detail
            # (raw exception text could leak paths/conn strings over SSE)
            import logging

            logging.getLogger(__name__).warning(
                "lineage agent stream failed: %s", exc)
            result["error"] = f"agent failed ({type(exc).__name__})"
        finally:
            done.set()

    start = time.time()
    threading.Thread(target=worker, daemon=True).start()

    def stream():
        sent = 0
        while True:
            finished = done.wait(0.3)
            events = collector.snapshot()
            for ev in events[sent:]:
                t = ev.get("type")
                if t == "text_delta":
                    yield _sse({"type": "delta", "text": ev.get("text", "")})
                elif t == "step":
                    yield _sse({"type": "step",
                                "iteration": ev.get("iteration"),
                                "max": ev.get("max"),
                                "phase": ev.get("phase", "")})
                elif t == "tool_call":
                    yield _sse({"type": "tool", "name": ev.get("name", "?"),
                                "input": ev.get("input") or {}})
            sent = len(events)
            if finished:
                break
        final: dict[str, Any] = {"type": "final",
                                 "answer": result.get("answer", ""),
                                 "mermaid": result.get("mermaid", "")}
        if "error" in result:
            final["error"] = result["error"]
        else:
            _log_elapsed(start, graph.stats(), query=req.question,
                         mode="agent")
        yield _sse(final)

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
