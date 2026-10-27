"""REST API for the Data Skew agent — FastAPI router.

Mount on the Gradio app's FastAPI instance to serve alongside the UI
(``seatunnel-agent ui --api``).  Endpoints:

  POST /api/skew/check  — static skew-pattern analysis of a SQL script
  GET  /api/skew/health — health check

plus the session-scoped React-page surface (connect / analyze / verify /
consistency / splitkey / runtime / history / presets) documented on each
endpoint below. ``/check`` stays the deterministic static scan: no LLM,
no database, nothing executed — safe to call from CI or other services.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import add_health, ms_since
from seatunnel_agent.common.utils import normalize_lang

from .detector import _DIALECT_ALIASES, DIALECTS
from .history import default_history

router = APIRouter(prefix="/api/skew", tags=["data_skew"])

_DIALECT_DESC = " | ".join(DIALECTS)


class SkewCheckRequest(BaseModel):
    sql: str = Field(..., min_length=1, description="SQL statement/script to analyze")
    dialect: str = Field("spark", description=_DIALECT_DESC)
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")


class SkewCheckResponse(BaseModel):
    report: str
    findings: list[dict[str, Any]]
    counts: dict[str, int]
    dialect: str
    elapsed_ms: int


@router.post("/check", response_model=SkewCheckResponse)
def check(req: SkewCheckRequest) -> SkewCheckResponse:
    from .agent import static_skew_report
    from .report import render_report

    start = time.time()
    raw = (req.dialect or "spark").strip().lower().replace(" ", "")
    dialect = _DIALECT_ALIASES.get(raw, raw)
    if dialect not in DIALECTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown dialect '{req.dialect}'; expected one of: {_DIALECT_DESC}",
        )
    lang = normalize_lang(req.lang)
    rep = static_skew_report(req.sql, dialect, lang)
    default_history().log(req.sql, rep, mode="static", source="api")
    return SkewCheckResponse(
        report=render_report(rep, lang),
        findings=[f.to_dict() for f in rep.findings],
        counts={"high": len(rep.high), "medium": len(rep.medium),
                "low": len(rep.low)},
        dialect=dialect,
        elapsed_ms=ms_since(start),
    )


add_health(router, "data_skew")


# ───────────────────────── React-page surface ─────────────────────────
# Session-scoped endpoints the React /dataskew page calls (the Gradio page
# held this state in gr.State). Guard messages come back both structured
# (code) and localized (message, via the backend dsk() dict) so the page
# renders them without duplicating backend i18n keys.

# Probe-capable datasources only (LIMIT-compatible engines) — mirrors the
# legacy connection panel restriction.
_PROBE_DS = ("hive", "sparksql", "mysql", "postgresql", "sqlite")


def _err_400(lang: str, exc: Exception) -> HTTPException:
    """Localized catch-all for probe/DB/LLM failures (legacy _err_md path)."""
    from .i18n import dsk

    sep = ": " if lang == "en" else "："
    return HTTPException(status_code=400, detail={
        "code": "dsk_error",
        "message": f"❌ **{dsk(lang, 'dsk_error')}**{sep}{exc}"})


def _guard(lang: str, code: str, **fmt: Any) -> HTTPException:
    from .i18n import dsk

    msg = dsk(lang, code)
    if fmt:
        msg = msg.format(**fmt)
    return HTTPException(status_code=400,
                         detail={"code": code, "message": msg})


def _get_session(session_id: str) -> Any:
    from .registry import get_registry

    session = get_registry().get(session_id or "")
    if session is None:
        raise HTTPException(status_code=404, detail="unknown session_id")
    return session


def _connected_or_400(session_id: str, lang: str, code: str) -> Any:
    session = _get_session(session_id)
    if not session.connected:
        raise _guard(lang, code)
    return session


def _cached_probes(session: Any, sql: str, pct: int) -> list:
    """Probe results for (sql, datasource, sampling), reusing the last run."""
    from .probe import extract_probe_targets, run_probes

    key = (sql, session.ds_type, pct)
    cached = session.cache.get(key)
    if cached is not None:
        return cached
    results = run_probes(session.executor, extract_probe_targets(sql),
                         ds_type=session.ds_type, sample_pct=pct)
    session.cache.put(key, results)
    return results


@router.post("/session")
def create_session() -> dict[str, str]:
    """Issue a new per-tab session in the skew connection registry."""
    from .registry import get_registry

    return {"session_id": get_registry().create().session_id}


class ConnectRequest(BaseModel):
    session_id: str
    ds_type: str = Field(..., description="hive|sparksql|mysql|postgresql|sqlite")
    host: str = ""
    port: str = ""
    database: str = ""
    username: str = ""
    password: str = ""
    lang: str = "en"


@router.post("/connect")
def connect(req: ConnectRequest) -> dict[str, Any]:
    """Connect the session's datasource (legacy do_connect, verbatim rules:
    sqlite ignores host, empty host falls back to .env config)."""
    from seatunnel_agent.agents.data.text2sql.executor.base import (
        DS_DEFAULTS,
        DatabaseConfig,
        config_from_env,
        create_executor,
    )

    from .i18n import dsk
    from .probe import ProbeCache

    session = _get_session(req.session_id)
    lang = normalize_lang(req.lang)
    ds = (req.ds_type or "").strip().lower()
    if ds not in _PROBE_DS:  # whitelist first (transpile fix-up precedent)
        raise _guard(lang, "dsk_preset_unsupported", t=ds)
    defaults = DS_DEFAULTS.get(ds, {})
    host = (req.host or "").strip()
    db = (req.database or "").strip() or str(defaults.get("database", ""))
    try:
        if ds == "sqlite":
            cfg = DatabaseConfig(ds_type="sqlite", host="", port=0, database=db)
        elif not host:
            cfg = config_from_env(ds)
            if cfg is None:
                raise RuntimeError(dsk(lang, "dsk_conn_no_env"))
        else:
            try:
                port_n = int((req.port or "").strip() or defaults.get("port", 0))
            except ValueError:
                port_n = int(defaults.get("port", 0))
            cfg = DatabaseConfig(
                ds_type=ds, host=host, port=port_n, database=db,
                username=(req.username or "").strip() or None,
                password=(req.password or "").strip() or None,
            )
        executor = create_executor(cfg)
        ok, info = executor.test_connection()
        if not ok:
            raise RuntimeError(info)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail={
            "code": "dsk_conn_fail",
            "message": dsk(lang, "dsk_conn_fail").format(err=exc)})
    status_line = dsk(lang, "dsk_conn_ok").format(info=info)
    with session.lock:
        session.executor = executor
        session.ds_type = ds
        session.status = status_line
        session.cache = ProbeCache()
    return {"status": status_line, "connected": True}


class SessionRequest(BaseModel):
    session_id: str
    lang: str = "en"


@router.post("/disconnect")
def disconnect(req: SessionRequest) -> dict[str, Any]:
    from .probe import ProbeCache

    session = _get_session(req.session_id)
    with session.lock:
        session.executor = None
        session.ds_type = ""
        session.status = ""
        session.cache = ProbeCache()
    return {"connected": False}


@router.get("/status")
def status(session_id: str) -> dict[str, Any]:
    session = _get_session(session_id)
    return {"connected": session.connected, "status": session.status,
            "ds_type": session.ds_type}


class AnalyzeRequest(BaseModel):
    sql: str = Field(..., min_length=1)
    dialect: str = "spark"
    mode: str = Field("static", description="static | llm")
    sample: int = Field(10, description="probe sampling percent (0 = full)")
    lang: str = "zh"
    session_id: str = Field("", description="optional — adds probe context "
                                            "to LLM mode when connected")


@router.post("/analyze")
def analyze(req: AnalyzeRequest) -> dict[str, Any]:
    """Legacy do_analyze: static scan, or LLM rewrite with probe context;
    LLM falling back to static yields ``llm_unavailable: true`` plus the
    banner already prefixed to the report (1:1 with the Gradio page)."""
    from seatunnel_agent.common.config import load_settings

    from .agent import DataSkewAgent, static_skew_report
    from .detector import normalize_dialect
    from .i18n import dsk
    from .probe import (
        effective_sample_pct,
        extract_probe_targets,
        probe_lines_for_prompt,
        render_probe_section,
    )
    from .report import render_report

    start = time.time()
    lang = normalize_lang(req.lang)
    dialect = normalize_dialect(req.dialect)
    sql = req.sql.strip()
    history = default_history()
    llm_unavailable = False
    optimized = ""
    if req.mode != "llm":
        rep = static_skew_report(sql, dialect, lang)
        report = render_report(rep, lang)
        history.log(sql, rep, mode="static", source="api")
    else:
        try:
            settings = load_settings()
        except RuntimeError:
            settings = None
        if settings is None:
            rep = static_skew_report(sql, dialect, lang)
            report = (dsk(lang, "dsk_llm_unavailable") + "\n\n"
                      + render_report(rep, lang))
            history.log(sql, rep, mode="static", source="api")
            llm_unavailable = True
        else:
            probe_ctx = probe_section = ""
            if req.session_id:
                session = _get_session(req.session_id)
                if session.connected and extract_probe_targets(sql):
                    pct = effective_sample_pct(session.ds_type,
                                               int(req.sample or 0))
                    try:
                        results = _cached_probes(session, sql, pct)
                        probe_ctx = probe_lines_for_prompt(results, lang)
                        probe_section = render_probe_section(
                            results, lang, dialect=dialect, sample_pct=pct)
                    except Exception:  # probe is best-effort context
                        probe_ctx = probe_section = ""
            agent = DataSkewAgent(settings, dialect=dialect, lang=lang)
            try:
                result = agent.analyze(sql, use_llm=True,
                                       probe_context=probe_ctx)
            except Exception as exc:  # legacy do_analyze caught Exception
                raise _err_400(lang, exc)
            report = result.markdown
            if probe_section:
                report = report.rstrip() + "\n\n" + probe_section
            optimized = result.optimized_sql
            history.log(sql, result.report, mode="llm", source="api")
    return {"report": report, "optimized_sql": optimized,
            "llm_unavailable": llm_unavailable, "elapsed_ms": ms_since(start)}


class VerifyRequest(BaseModel):
    session_id: str
    sql: str
    report: str = ""
    dialect: str = "spark"
    sample: int = 10
    lang: str = "en"


@router.post("/verify")
def verify(req: VerifyRequest) -> dict[str, Any]:
    """Legacy do_verify: live probes appended into the report section."""
    from .detector import normalize_dialect
    from .probe import (
        effective_sample_pct,
        extract_probe_targets,
        render_probe_section,
    )
    from .sections import PROBE_HEAD_RE, append_section

    lang = normalize_lang(req.lang)
    session = _connected_or_400(req.session_id, lang, "dsk_verify_need_conn")
    sql = (req.sql or "").strip()
    if not sql:
        raise _guard(lang, "dsk_empty_sql")
    pct = effective_sample_pct(session.ds_type, int(req.sample or 0))
    try:
        results = _cached_probes(session, sql, pct)
        section = render_probe_section(
            results, lang, dialect=normalize_dialect(req.dialect),
            sample_pct=pct)
    except Exception as exc:  # legacy do_verify caught Exception → _err_md
        raise _err_400(lang, exc)
    default_history().log_verify(
        sql, targets=len(extract_probe_targets(sql)),
        confirmed=sum(1 for r in results if r.verdict == "confirmed"),
        source="api")
    return {"report": append_section(req.report, section, PROBE_HEAD_RE),
            "status": session.status}


class ConsistencyRequest(BaseModel):
    session_id: str
    sql: str
    optimized: str = ""
    report: str = ""
    lang: str = "en"


@router.post("/consistency")
def consistency(req: ConsistencyRequest) -> dict[str, Any]:
    """Legacy do_consistency: run original vs optimized, append section."""
    from .consistency import check_consistency, render_consistency_section
    from .sections import CST_HEAD_RE, append_section

    lang = normalize_lang(req.lang)
    session = _connected_or_400(req.session_id, lang, "dsk_verify_need_conn")
    sql = (req.sql or "").strip()
    if not sql:
        raise _guard(lang, "dsk_empty_sql")
    if not (req.optimized or "").strip():
        raise _guard(lang, "cst_need_opt")
    try:
        res = check_consistency(session.executor, sql, req.optimized)
        section = render_consistency_section(res, lang)
    except Exception as exc:  # legacy do_consistency caught Exception
        raise _err_400(lang, exc)
    return {"report": append_section(req.report, section, CST_HEAD_RE),
            "status": session.status}


class SplitKeyRequest(BaseModel):
    session_id: str
    conf: str
    report: str = ""
    sample: int = 10
    lang: str = "en"


@router.post("/splitkey")
def splitkey(req: SplitKeyRequest) -> dict[str, Any]:
    """Legacy do_splitkey: measured split-key check over a SeaTunnel conf;
    ``patched_conf`` carries the rewritten config text when the measured
    best key differs (single-source configs only, CLI --apply guard)."""
    from .i18n import dsk
    from .probe import effective_sample_pct
    from .sections import SPK_HEAD_RE, append_section
    from .splitkey import (
        SplitKeyError,
        apply_split_key,
        pick_best_key,
        render_splitkey_multi,
        run_split_key_multi,
        sink_key_section,
        splitkey_metrics,
    )

    lang = normalize_lang(req.lang)
    session = _connected_or_400(req.session_id, lang, "spk_need_conn")
    conf_text = (req.conf or "").strip()
    if not conf_text:
        raise _guard(lang, "spk_empty_conf")
    pct = effective_sample_pct(session.ds_type, int(req.sample or 0))
    history = default_history()
    try:
        results, total = run_split_key_multi(
            session.executor, conf_text,
            ds_type=session.ds_type, sample_pct=pct)
        previous_by_table = {
            spec.table: prev for spec, _, _ in results
            if (prev := history.last_splitkey(spec.table))}
        section = render_splitkey_multi(
            results, lang, sample_pct=pct, total=total,
            previous_by_table=previous_by_table)
        snk = sink_key_section(session.executor, conf_text,
                               ds_type=session.ds_type, sample_pct=pct,
                               lang=lang, log_source="api")
        if snk:
            section = section + "\n" + snk
    except SplitKeyError as exc:
        raise HTTPException(status_code=400, detail={
            "code": exc.key,
            "message": dsk(lang, exc.key).format(err=exc.arg)})
    except Exception as exc:  # legacy do_splitkey caught Exception
        raise _err_400(lang, exc)
    for spec, configured, candidates in results:
        history.log_splitkey(
            spec.table, spec.partition_column,
            configured.verdict(spec.tasks) if configured else "none",
            candidates=len(candidates), source="api",
            **splitkey_metrics(configured))
    patched: str | None = None
    if total == 1:
        spec, configured, candidates = results[0]
        best = pick_best_key(spec, configured, candidates)
        if best is not None and best.column != spec.partition_column:
            try:
                patched = apply_split_key(
                    conf_text, spec, best.column,
                    partition_num=max(spec.partition_num, spec.tasks))
            except SplitKeyError:
                patched = None
    return {"report": append_section(req.report, section, SPK_HEAD_RE),
            "status": session.status, "patched_conf": patched}


def _runtime_response(stages: list, label: str, report_cur: str,
                      lang: str, session_status: str) -> dict[str, Any]:
    from .runtime import diagnose_and_log
    from .sections import RT_HEAD_RE, append_section

    section, _, _ = diagnose_and_log(
        default_history(), stages, label, lang, source="api")
    return {"report": append_section(report_cur, section, RT_HEAD_RE),
            "status": session_status}


class HistoryServerRequest(BaseModel):
    url: str = ""
    app_id: str = ""
    report: str = ""
    lang: str = "en"
    session_id: str = ""


@router.post("/runtime/flink")
def runtime_flink(req: HistoryServerRequest) -> dict[str, Any]:
    """Runtime diagnosis via the Flink REST API (SeaTunnel on Flink):
    url = Flink REST base (e.g. http://host:8081), app_id = Flink job id."""
    from .i18n import dsk
    from .runtime import RuntimeSkewError, analyze_flink

    lang = normalize_lang(req.lang)
    if not (req.url or "").strip() or not (req.app_id or "").strip():
        raise _guard(lang, "rt_need_url")
    try:
        stages, label = analyze_flink(req.url, req.app_id)
    except RuntimeSkewError as exc:
        raise HTTPException(status_code=400, detail={
            "code": exc.key,
            "message": dsk(lang, exc.key).format(err=exc.arg)})
    status_line = ""
    if req.session_id:
        status_line = _get_session(req.session_id).status
    return _runtime_response(stages, label, req.report, lang, status_line)


@router.post("/runtime/history-server")
def runtime_history_server(req: HistoryServerRequest) -> dict[str, Any]:
    from .i18n import dsk
    from .runtime import RuntimeSkewError, analyze_history_server

    lang = normalize_lang(req.lang)
    if not (req.url or "").strip() or not (req.app_id or "").strip():
        raise _guard(lang, "rt_need_url")
    try:
        stages, label = analyze_history_server(req.url, req.app_id)
    except RuntimeSkewError as exc:
        raise HTTPException(status_code=400, detail={
            "code": exc.key,
            "message": dsk(lang, exc.key).format(err=exc.arg)})
    status_line = ""
    if req.session_id:
        status_line = _get_session(req.session_id).status
    return _runtime_response(stages, label, req.report, lang, status_line)


@router.post("/runtime/eventlog")
async def runtime_eventlog(file: UploadFile, report: str = "",
                           lang: str = "en",
                           session_id: str = "") -> dict[str, Any]:
    """Multipart Spark event-log upload (legacy do_runtime_file)."""
    import shutil
    import tempfile
    from pathlib import Path

    from .i18n import dsk
    from .runtime import RuntimeSkewError, parse_eventlog

    lang = normalize_lang(lang)
    tmp_dir = Path(tempfile.mkdtemp(prefix="dataskew_rt_"))
    tmp = tmp_dir / (file.filename or "eventlog")
    tmp.write_bytes(await file.read())
    try:
        stages, label = parse_eventlog(str(tmp))
    except RuntimeSkewError as exc:
        raise HTTPException(status_code=400, detail={
            "code": exc.key,
            "message": dsk(lang, exc.key).format(err=exc.arg)})
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    if str(label).startswith("tmp"):
        label = "event log"
    status_line = ""
    if session_id:
        status_line = _get_session(session_id).status
    return _runtime_response(stages, label, report, lang, status_line)


@router.get("/drift")
def drift(table: str = "", lang: str = "zh") -> dict[str, Any]:
    """Skew drift per table: latest splitkey measurement vs its baseline.

    Read-only over the patrol history — same verdicts as the skew-drift
    CLI; ``text`` is the shared bilingual rendering for the trend card."""
    from .drift import compute_drift, render_drift

    lng = normalize_lang(lang)
    history = default_history()
    tables = [table] if table else history.splitkey_tables()
    items: list[dict[str, Any]] = []
    for t in tables:
        result = compute_drift(t, history.splitkey_trend(t, n=50))
        items.append({
            "table": result.table,
            "column": result.column,
            "verdict": result.verdict,
            "samples": result.samples,
            "drifts": [{"metric": d.metric, "baseline": d.baseline,
                        "current": d.current, "delta": d.delta}
                       for d in result.drifts],
            "hot_value": {"prev": result.top1_value_prev,
                          "cur": result.top1_value_cur,
                          "changed": result.hot_value_changed},
            "text": render_drift(result, lng),
        })
    return {"items": items}


@router.get("/history")
def history_recent(n: int = 20) -> dict[str, Any]:
    """Recent analysis history records (newest first), raw — the React
    page renders the table and reloads sql/dialect client-side."""
    return {"records": default_history().recent(max(1, min(int(n), 100)))}


@router.get("/presets")
def presets_list() -> dict[str, Any]:
    """Names of saved connection presets (shared store with Settings /
    Data Comparison); unsupported ds_types are flagged, not hidden."""
    from seatunnel_agent.agents.data.data_comparison.presets import (
        ConnectionPresetsStore,
    )

    try:
        entries = ConnectionPresetsStore().list()
    except Exception:
        entries = []
    return {"presets": [
        {"name": p.get("name", ""),
         "ds_type": str(p.get("ds_type") or "").lower(),
         "supported": str(p.get("ds_type") or "").lower() in _PROBE_DS}
        for p in entries if p.get("name")]}


@router.get("/presets/{name}")
def presets_get(name: str) -> dict[str, Any]:
    """One preset's connection form values (password included — the
    legacy page filled the password box the same way)."""
    from seatunnel_agent.agents.data.data_comparison.presets import (
        ConnectionPresetsStore,
    )

    try:
        p = ConnectionPresetsStore().get_by_name(name)
    except Exception:
        p = None
    if not p:
        raise HTTPException(status_code=404, detail="unknown preset")
    return {"name": p.get("name", ""),
            "ds_type": str(p.get("ds_type") or "").lower(),
            "host": str(p.get("host") or ""),
            "port": str(p.get("port") or ""),
            "database": str(p.get("database") or ""),
            "username": str(p.get("username") or ""),
            "password": str(p.get("password") or "")}
