"""Generation features + templates (ticket 08) — Gradio-free.

Sync-config generation (+ download with real passwords), diff-SQL
generation, lineage from SQL, multi-environment compare, and comparison
templates (CRUD + batch run). The pure functions are extracted 1:1 from
the legacy ``ui.py`` closures; the :data:`router` is included by
``api.py`` so the React page reaches them under ``/api/datacompare``.

Downloaded sync configs carry the *real* passwords; the rendered HTML
only ever shows the masked config (legacy behavior). The file is written
to a temp path and handed out by an opaque ``download_id`` so the
passwords never ride in a JSON body.
"""

from __future__ import annotations

import os
import tempfile
import threading
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from seatunnel_agent.agents.data.data_comparison.comparator import (
    build_aggregate_sql,
    build_count_sql,
    build_row_count_result,
    compare_aggregates,
    compare_schemas,
    generate_diff_sql,
    generate_sync_config,
    get_upstream_tables,
    is_numeric_type,
    parse_column_mapping,
    run_parallel,
)
from seatunnel_agent.agents.data.data_comparison.i18n import dc
from seatunnel_agent.agents.data.data_comparison.registry import (
    SessionState,
    get_registry,
)
from seatunnel_agent.agents.data.data_comparison.ui_cards import (
    build_aggregate_card,
    build_batch_template_card,
    build_count_card,
    build_diff_sql_card,
    build_lineage_card,
    build_schema_diff_card,
)
from seatunnel_agent.agents.data.data_comparison.ui_shared import (
    _MAX_AGG_COLUMNS,
    _PRESETS_STORE,
    _TEMPLATES_STORE,
    _error_html,
    _esc_html,
    _log,
    _validate_where,
)
from seatunnel_agent.agents.data.text2sql.executor import (
    DatabaseConfig,
    create_executor,
)

router = APIRouter(tags=["datacompare"])

# Sync-config downloads: opaque id -> temp file with the real passwords.
_SYNC_DOWNLOADS: dict[str, str] = {}
_SYNC_DOWNLOADS_LOCK = threading.Lock()


# ── sync-config generation (legacy ui.py `_gen_sync_config`) ─────────


def gen_sync_config(
    session: SessionState, table_a: str, table_b: str,
    col_mapping_str: str = "", lang_val: str = "en",
) -> tuple[str, str | None]:
    """Masked-config HTML + temp file path holding the real-password config.

    Returns ``(html, path)``; ``path`` is ``None`` on any guard/error.
    """
    with session.lock:
        ex_a = session.executor_a
        ex_b = session.executor_b
    if not ex_a or not ex_b:
        return dc(lang_val, "dc_connect_both"), None
    if not table_a or not table_b:
        return dc(lang_val, "dc_select_tables"), None
    try:
        cfg_a, cfg_b = ex_a.config, ex_b.config
        mapping = parse_column_mapping(col_mapping_str) if col_mapping_str else None

        def _gen(pwd_a: str | None, pwd_b: str | None) -> str:
            return generate_sync_config(
                cfg_a.ds_type, cfg_a.host, cfg_a.port, cfg_a.database,
                cfg_a.username, pwd_a, table_a,
                cfg_b.ds_type, cfg_b.host, cfg_b.port, cfg_b.database,
                cfg_b.username, pwd_b, table_b,
                column_mapping=mapping,
            )

        # Page shows a masked config; the real passwords only go to the
        # downloadable file so they never land in the rendered HTML.
        masked_text = _gen(
            "******" if cfg_a.password else None,
            "******" if cfg_b.password else None,
        )
        full_text = _gen(cfg_a.password, cfg_b.password)
        fd, tmp_path = tempfile.mkstemp(prefix="seatunnel_sync_", suffix=".conf")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(full_text)

        header = (f'<div style="color:#16a34a;font-weight:600;margin-bottom:8px;">'
                  f'✅ {dc(lang_val, "dc_sync_generated")}</div>')
        code_block = (f'<pre style="background:#1e293b;color:#e2e8f0;padding:16px;'
                      f'border-radius:8px;overflow-x:auto;font-size:12px;">'
                      f'{_esc_html(masked_text)}</pre>')
        return header + code_block, tmp_path
    except Exception as e:
        return _error_html(lang_val, e), None


# ── diff-SQL generation (legacy ui.py `_gen_diff_sql_fn`) ────────────


def gen_diff_sql_html(session: SessionState, table_b: str,
                      lang_val: str = "en") -> str:
    with session.lock:
        report = session.last_report
    if not report or not report.keyed_diff:
        return dc(lang_val, "dc_diff_sql_no_diff")
    try:
        with session.lock:
            ex_b = session.executor_b
        ds_type = ex_b.config.ds_type if ex_b else "mysql"
        sql = generate_diff_sql(report.keyed_diff, table_b, ds_type)
        return build_diff_sql_card(sql, lang_val)
    except Exception as e:
        return _error_html(lang_val, e)


# ── lineage (legacy ui.py `_show_lineage_fn`) ────────────────────────


def lineage_html(table_a: str, lineage_sql_str: str,
                 lang_val: str = "en") -> str:
    if not table_a:
        return dc(lang_val, "dc_select_tables")
    if not lineage_sql_str or not lineage_sql_str.strip():
        return dc(lang_val, "dc_lineage_hint")
    try:
        sqls = [s.strip() for s in lineage_sql_str.strip().split("\n") if s.strip()]
        upstream = get_upstream_tables(table_a, sqls)
        return build_lineage_card(table_a, upstream, lang_val)
    except Exception as e:
        return _error_html(lang_val, e)


# ── multi-environment compare (legacy ui.py `_compare_environments_fn`) ─


def compare_environments_html(env_a: str, env_b: str, table_name: str,
                              lang_val: str = "en", where_val: str = "",
                              ) -> str:
    if not env_a.strip() or not env_b.strip():
        return dc(lang_val, "dc_env_hint")
    if not table_name.strip():
        return dc(lang_val, "dc_select_tables")
    ok, msg = _validate_where(where_val, lang_val)
    if not ok:
        return msg
    presets = _PRESETS_STORE.list()
    pa = next((p for p in presets if p.get("environment", "") == env_a.strip()), None)
    pb = next((p for p in presets if p.get("environment", "") == env_b.strip()), None)
    if not pa or not pb:
        return dc(lang_val, "dc_env_hint")
    try:
        cfg_a = DatabaseConfig(
            ds_type=pa["ds_type"], host=pa["host"], port=pa["port"],
            database=pa["database"], username=pa.get("username"),
            password=pa.get("password"),
        )
        cfg_b = DatabaseConfig(
            ds_type=pb["ds_type"], host=pb["host"], port=pb["port"],
            database=pb["database"], username=pb.get("username"),
            password=pb.get("password"),
        )
        ex_a = create_executor(cfg_a)
        ex_b = create_executor(cfg_b)
        tbl = table_name.strip()
        cards: list[str] = []
        label_a = f"{tbl} ({env_a})"
        label_b = f"{tbl} ({env_b})"

        # Schema comparison
        desc_a, desc_b = run_parallel(
            lambda: ex_a.describe_table(tbl),
            lambda: ex_b.describe_table(tbl),
        )
        ca_list = [{"name": c.name, "type": c.dtype} for c in desc_a.columns]
        cb_list = [{"name": c.name, "type": c.dtype} for c in desc_b.columns]
        schema_result = compare_schemas(ca_list, cb_list, label_a, label_b)
        cards.append(build_schema_diff_card(schema_result, lang_val))

        # Count comparison
        sql_ca = build_count_sql(tbl, where_val)
        sql_cb = build_count_sql(tbl, where_val)
        ra, rb = run_parallel(
            lambda: ex_a.run(sql_ca, max_rows=1),
            lambda: ex_b.run(sql_cb, max_rows=1),
        )
        ca = int(ra.rows[0][0]) if ra.rows else 0
        cb = int(rb.rows[0][0]) if rb.rows else 0
        count_result = build_row_count_result(label_a, ca, label_b, cb)
        cards.append(build_count_card(count_result, lang_val))

        # Aggregate comparison on shared numeric columns
        names_b = {c.name.lower() for c in desc_b.columns}
        shared_num = [
            c.name for c in desc_a.columns
            if is_numeric_type(c.dtype) and c.name.lower() in names_b
        ]
        if shared_num:
            agg_sql_a = build_aggregate_sql(tbl, shared_num[:_MAX_AGG_COLUMNS],
                                            where_val, ds_type=ex_a.config.ds_type)
            agg_sql_b = build_aggregate_sql(tbl, shared_num[:_MAX_AGG_COLUMNS],
                                            where_val, ds_type=ex_b.config.ds_type)
            agg_ra, agg_rb = run_parallel(
                lambda: ex_a.run(agg_sql_a, max_rows=200),
                lambda: ex_b.run(agg_sql_b, max_rows=200),
            )
            agg_result = compare_aggregates(
                label_a, agg_ra.rows[0] if agg_ra.rows else (),
                label_b, agg_rb.rows[0] if agg_rb.rows else (),
                shared_num[:_MAX_AGG_COLUMNS],
            )
            cards.append(build_aggregate_card(agg_result, lang_val))

        # Header recolored from the legacy indigo (#6366f1) to the page's
        # ink token — blue/purple is forbidden by the project UI rules.
        header = (f'<h4 style="color:var(--ink,#334155);">'
                  f'{dc(lang_val, "dc_env_compare_result")}</h4>')
        return header + "\n".join(cards)
    except Exception as e:
        return _error_html(lang_val, e)


# ── template batch run (legacy ui.py `_batch_templates_fn`) ──────────


def batch_templates_html(session: SessionState, selected_names: list[str],
                         lang_val: str = "en") -> str:
    if not selected_names:
        return dc(lang_val, "dc_batch_templates_hint")
    with session.lock:
        ex_a = session.executor_a
        ex_b = session.executor_b
    if ex_a is None or ex_b is None:
        return dc(lang_val, "dc_connect_both")
    results: list[dict[str, Any]] = []
    for name in selected_names:
        tmpl = _TEMPLATES_STORE.get_by_name(name)
        if not tmpl:
            results.append({"name": name, "status": "skip", "detail": "not found"})
            continue
        try:
            ta = tmpl.get("table_a", "")
            tb = tmpl.get("table_b", "")
            wh = tmpl.get("where_clause", "")

            # Count comparison
            count_sql_a = build_count_sql(ta, wh)
            count_sql_b = build_count_sql(tb, wh)
            ra, rb = run_parallel(
                lambda: ex_a.run(count_sql_a, max_rows=1),
                lambda: ex_b.run(count_sql_b, max_rows=1),
            )
            cnt_a = int(ra.rows[0][0]) if ra.rows else 0
            cnt_b = int(rb.rows[0][0]) if rb.rows else 0

            # Schema comparison
            schema_changes = 0
            try:
                desc_a, desc_b = run_parallel(
                    lambda: ex_a.describe_table(ta),
                    lambda: ex_b.describe_table(tb),
                )
                ca_list = [{"name": c.name, "type": c.dtype} for c in desc_a.columns]
                cb_list = [{"name": c.name, "type": c.dtype} for c in desc_b.columns]
                schema_result = compare_schemas(ca_list, cb_list, ta, tb)
                schema_changes = len(schema_result.items) if schema_result.has_changes else 0
            except Exception:
                _log.warning("Batch template %r: schema comparison failed",
                             name, exc_info=True)
                desc_a = desc_b = None

            # Aggregate comparison on shared numeric columns
            agg_mismatches = 0
            try:
                if desc_a and desc_b:
                    names_b = {c.name.lower() for c in desc_b.columns}
                    shared_num = [
                        c.name for c in desc_a.columns
                        if is_numeric_type(c.dtype) and c.name.lower() in names_b
                    ]
                    if shared_num:
                        agg_sql_a = build_aggregate_sql(
                            ta, shared_num[:_MAX_AGG_COLUMNS], wh,
                            ds_type=ex_a.config.ds_type)
                        agg_sql_b = build_aggregate_sql(
                            tb, shared_num[:_MAX_AGG_COLUMNS], wh,
                            ds_type=ex_b.config.ds_type)
                        agg_ra, agg_rb = run_parallel(
                            lambda: ex_a.run(agg_sql_a, max_rows=200),
                            lambda: ex_b.run(agg_sql_b, max_rows=200),
                        )
                        agg_result = compare_aggregates(
                            ta, agg_ra.rows[0] if agg_ra.rows else (),
                            tb, agg_rb.rows[0] if agg_rb.rows else (),
                            shared_num[:_MAX_AGG_COLUMNS],
                        )
                        agg_mismatches = agg_result.mismatches
            except Exception:
                _log.warning("Batch template %r: aggregate comparison failed",
                             name, exc_info=True)

            passed = cnt_a == cnt_b and schema_changes == 0 and agg_mismatches == 0
            results.append({
                "name": name, "table_a": ta, "table_b": tb,
                "count_a": cnt_a, "count_b": cnt_b,
                "schema_changes": schema_changes,
                "agg_mismatches": agg_mismatches,
                "status": "pass" if passed else "fail",
            })
        except Exception as exc:
            results.append({"name": name, "status": "fail", "detail": str(exc)})
    return build_batch_template_card(results, lang_val)


# ── REST endpoints ──────────────────────────────────────────────────


def _get_session(session_id: str) -> SessionState:
    session = get_registry().get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown session_id")
    return session


class SyncConfigRequest(BaseModel):
    session_id: str
    table_a: str = ""
    table_b: str = ""
    column_mapping: str = ""
    lang: str = "en"


@router.post("/generate/sync-config")
def generate_sync_config_endpoint(req: SyncConfigRequest) -> dict[str, Any]:
    """Masked config HTML + download_id for the real-password .conf file."""
    session = _get_session(req.session_id)
    html, path = gen_sync_config(session, req.table_a, req.table_b,
                                 req.column_mapping, req.lang)
    download_id: str | None = None
    if path is not None:
        download_id = uuid.uuid4().hex
        with _SYNC_DOWNLOADS_LOCK:
            _SYNC_DOWNLOADS[download_id] = path
    return {"html": html, "download_id": download_id}


@router.get("/generate/sync-config/download")
def download_sync_config(download_id: str = Query(alias="id")) -> FileResponse:
    """The generated .conf with real passwords, as an attachment."""
    with _SYNC_DOWNLOADS_LOCK:
        path = _SYNC_DOWNLOADS.get(download_id)
    if path is None or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="unknown download id")
    return FileResponse(path, filename="seatunnel_sync.conf",
                        media_type="application/octet-stream")


class DiffSqlRequest(BaseModel):
    session_id: str
    table_a: str = ""
    table_b: str = ""
    lang: str = "en"


@router.post("/generate/diff-sql")
def generate_diff_sql_endpoint(req: DiffSqlRequest) -> dict[str, str]:
    """INSERT/UPDATE/DELETE SQL card from the last keyed diff."""
    session = _get_session(req.session_id)
    return {"html": gen_diff_sql_html(session, req.table_b, req.lang)}


class LineageRequest(BaseModel):
    table: str = ""
    sqls: str = ""
    lang: str = "en"


@router.post("/lineage")
def lineage_endpoint(req: LineageRequest) -> dict[str, str]:
    """Upstream-dependency card traced from the given SQL statements."""
    return {"html": lineage_html(req.table, req.sqls, req.lang)}


class EnvCompareRequest(BaseModel):
    env_a: str = ""
    env_b: str = ""
    table: str = ""
    where: str = ""
    lang: str = "en"


@router.post("/compare/environments")
def compare_environments_endpoint(req: EnvCompareRequest) -> dict[str, str]:
    """Schema/count/aggregate cards for one table across two preset envs."""
    return {"html": compare_environments_html(
        req.env_a, req.env_b, req.table, req.lang, req.where)}


class TemplateSaveRequest(BaseModel):
    name: str
    table_a: str = ""
    table_b: str = ""
    where_clause: str = ""
    key_columns: str = ""
    threshold: str = ""
    column_mapping: str = ""
    sample_strategy: str = "TOP N"
    watermark_column: str = ""
    quality_rules: str = ""
    webhook_url: str = ""
    notify_on_fail: bool = False
    masking_enabled: bool = True


@router.get("/templates")
def list_templates() -> dict[str, Any]:
    """Summaries for the template dropdowns."""
    return {
        "templates": [
            {
                "id": t.get("id", ""),
                "name": t.get("name", ""),
                "table_a": t.get("table_a", ""),
                "table_b": t.get("table_b", ""),
                "created_at": t.get("created_at", ""),
            }
            for t in _TEMPLATES_STORE.list()
        ]
    }


@router.post("/templates")
def save_template(req: TemplateSaveRequest) -> dict[str, Any]:
    """Save (upsert by name) a comparison template."""
    try:
        _TEMPLATES_STORE.save(
            name=req.name, table_a=req.table_a, table_b=req.table_b,
            where_clause=req.where_clause, key_columns=req.key_columns,
            threshold=req.threshold, column_mapping=req.column_mapping,
            sample_strategy=req.sample_strategy,
            watermark_column=req.watermark_column,
            quality_rules=req.quality_rules, webhook_url=req.webhook_url,
            notify_on_fail=req.notify_on_fail,
            masking_enabled=req.masking_enabled,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "name": req.name.strip()}


@router.get("/templates/{name}")
def load_template(name: str) -> dict[str, Any]:
    """Full template to fill the page form client-side."""
    tmpl = _TEMPLATES_STORE.get_by_name(name)
    if tmpl is None:
        raise HTTPException(status_code=404, detail="unknown template")
    return tmpl


@router.delete("/templates/{name}")
def delete_template(name: str) -> dict[str, Any]:
    """Delete a template by name (legacy deletes the selected name)."""
    tmpl = _TEMPLATES_STORE.get_by_name(name)
    if tmpl is None or not _TEMPLATES_STORE.delete(tmpl.get("id", "")):
        raise HTTPException(status_code=404, detail="unknown template")
    return {"ok": True}


class BatchRunRequest(BaseModel):
    session_id: str
    names: list[str] = []
    lang: str = "en"


@router.post("/templates/batch-run")
def batch_run_templates(req: BatchRunRequest) -> dict[str, str]:
    """Combined batch-result card over the selected templates (legacy F6)."""
    session = _get_session(req.session_id)
    return {"html": batch_templates_html(session, req.names, req.lang)}
