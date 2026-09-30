"""Gradio page for the Data Skew agent.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("Data Skew", "/dataskew")``. Static mode is pure local rule
scanning; LLM mode also rewrites the SQL following the fixed 5-step
workflow. The page is bilingual (EN/ZH) following the same switch pattern
as the SQL Review / Data Comparison pages.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

import gradio as gr

from .config import load_settings
from .data_skew.agent import DataSkewAgent, static_skew_report
from .data_skew.consistency import check_consistency, render_consistency_section
from .data_skew.detector import DIALECTS, normalize_dialect
from .data_skew.history import default_history
from .data_skew.i18n import dsk
from .data_skew.report import render_report
from .data_skew.probe import (
    ProbeCache,
    effective_sample_pct,
    extract_probe_targets,
    probe_lines_for_prompt,
    render_probe_section,
    run_probes,
)
from .data_skew.runtime import (
    RuntimeSkewError,
    analyze_history_server,
    parse_eventlog,
    render_runtime_section,
)
from .data_skew.splitkey import (
    SplitKeyError,
    apply_split_key,
    pick_best_key,
    render_splitkey_multi,
    run_split_key_multi,
)
from .text2sql.executor.base import (
    DIALECT_NAMES,
    DS_DEFAULTS,
    DatabaseConfig,
    config_from_env,
    create_executor,
)

_DIALECT_LABELS = {
    "spark": "Spark SQL (Spark 3)",
    "maxcompute": "MaxCompute SQL",
    "hive": "Hive SQL",
}
_DIALECT_CHOICES = [(_DIALECT_LABELS[d], d) for d in DIALECTS]

# Probe queries use GROUP BY ... ORDER BY ... LIMIT — restrict the
# connection panel to LIMIT-compatible engines.
_PROBE_DS = ("hive", "sparksql", "mysql", "postgresql", "sqlite")
_CONN_DS_CHOICES = [(DIALECT_NAMES[d], d) for d in _PROBE_DS]

_DEFAULT_LANG = "en"


def _mode_choices(lang: str) -> list[tuple[str, str]]:
    return [(dsk(lang, "dsk_mode_static"), "static"),
            (dsk(lang, "dsk_mode_llm"), "llm")]


def _sample_choices(lang: str) -> list[tuple[str, int]]:
    return [(dsk(lang, "dsk_sample_full"), 0), ("10%", 10), ("1%", 1)]


def _err_md(exc: Exception, lang: str) -> str:
    sep = ": " if lang == "en" else "："
    return f"❌ **{dsk(lang, 'dsk_error')}**{sep}{exc}"


def _head_re(*heads: str) -> re.Pattern[str]:
    # Line-anchored so a report merely *quoting* the heading mid-sentence
    # is not matched there.
    return re.compile(
        r"(?m)^[ \t]{0,3}#{2,3}\s*(?:"
        + "|".join(re.escape(h.lstrip("# ")) for h in heads)
        + r")\s*$"
    )


_PROBE_HEAD_RE = _head_re(dsk("zh", "prb_section"), dsk("en", "prb_section"))
_CST_HEAD_RE = _head_re(dsk("zh", "cst_section"), dsk("en", "cst_section"))
_SPK_HEAD_RE = _head_re(dsk("zh", "spk_section"), dsk("en", "spk_section"))
_RT_HEAD_RE = _head_re(dsk("zh", "rt_section"), dsk("en", "rt_section"))
_NEXT_H2_RE = re.compile(r"(?m)^[ \t]{0,3}#{1,2}\s")

# Cookie the Data Comparison page sets alongside the SQL handoff so the
# user lands here with side B's connection pre-filled (no password).
CONN_HANDOFF_COOKIE = "st_dataskew_conn"


def parse_conn_handoff(raw: str | None) -> dict | None:
    """Decode the ``st_dataskew_conn`` cookie into a connection dict, or
    None when absent/garbled. Pure so it is unit-testable."""
    import json
    from urllib.parse import unquote

    if not raw:
        return None
    try:
        data = json.loads(unquote(raw))
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    return {
        "ds_type": str(data.get("ds_type") or "").lower(),
        "host": str(data.get("host") or ""),
        "port": str(data.get("port") or ""),
        "database": str(data.get("database") or ""),
        "username": str(data.get("username") or ""),
    }


def _remove_section(report: str, head_re: re.Pattern[str]) -> str:
    """Drop one appended '## …' section (up to the next h1/h2) from the report."""
    m = head_re.search(report)
    if not m:
        return report
    nxt = _NEXT_H2_RE.search(report, m.end())
    end = nxt.start() if nxt else len(report)
    return (report[: m.start()].rstrip() + "\n\n" + report[end:].lstrip()).strip()


def render_data_skew_page(app: gr.Blocks) -> None:
    t0 = lambda k: dsk(_DEFAULT_LANG, k)  # noqa: E731 — initial labels

    # marker: body:has(.st-scroll-page) re-enables page scrolling
    gr.HTML('<div class="st-scroll-page" style="display:none"></div>')

    with gr.Row():
        title_md = gr.Markdown(f"{t0('dsk_title')}\n{t0('dsk_subtitle')}")
        home_btn = gr.Button("\U0001f3e0", size="sm", scale=0,
                             elem_classes=["st-home-btn"])
    lang_state = gr.State(_DEFAULT_LANG)

    with gr.Row():
        with gr.Column(scale=3, elem_classes=["dsk-input-col"]):
            sql_box = gr.Textbox(
                label="SQL", lines=14, max_lines=14,
                placeholder=t0("dsk_sql_placeholder"),
                buttons=["copy"], elem_id="dsk-sql-box",
            )
            with gr.Row():
                dialect_dd = gr.Dropdown(
                    choices=_DIALECT_CHOICES, value="spark",
                    label=t0("dsk_dialect"),
                )
                mode_radio = gr.Radio(
                    choices=_mode_choices(_DEFAULT_LANG),
                    value="static", label=t0("dsk_mode"),
                )
            with gr.Row():
                analyze_btn = gr.Button(t0("dsk_analyze_btn"), variant="primary")
                upload_btn = gr.UploadButton(t0("dsk_upload_btn"), size="sm",
                                             scale=0, min_width=140,
                                             file_types=[".sql", ".txt", ".hql"])
                clear_btn = gr.Button(t0("dsk_clear_btn"), scale=0, min_width=80)
            with gr.Accordion(t0("dsk_conn_accordion"), open=False) as conn_acc:
                with gr.Row():
                    preset_dd = gr.Dropdown(choices=[], value=None,
                                            label=t0("dsk_preset_dd"))
                    preset_load_btn = gr.Button(t0("dsk_preset_load"),
                                                size="sm", scale=0)
                with gr.Row():
                    ds_dd = gr.Dropdown(choices=_CONN_DS_CHOICES, value="hive",
                                        label=t0("dsk_ds_type"))
                    # default 10%: a casual verify on a production-size
                    # table must not full-scan; engines without TABLESAMPLE
                    # fall back to full via effective_sample_pct()
                    sample_dd = gr.Dropdown(choices=_sample_choices(_DEFAULT_LANG),
                                            value=10, label=t0("dsk_sample"))
                with gr.Row():
                    host_tb = gr.Textbox(label=t0("dsk_host"),
                                         placeholder="empty → .env")
                    port_tb = gr.Textbox(label=t0("dsk_port"), placeholder="10000")
                with gr.Row():
                    db_tb = gr.Textbox(label=t0("dsk_db"), placeholder="default")
                    user_tb = gr.Textbox(label=t0("dsk_user"))
                    pwd_tb = gr.Textbox(label=t0("dsk_pwd"), type="password")
                with gr.Row():
                    connect_btn = gr.Button(t0("dsk_connect_btn"), size="sm")
                    verify_btn = gr.Button(t0("dsk_verify_btn"), size="sm",
                                           variant="secondary")
                    cst_btn = gr.Button(t0("cst_btn"), size="sm",
                                        variant="secondary")
                conn_status = gr.Markdown(t0("dsk_conn_status_none"))
            with gr.Accordion(t0("spk_accordion"), open=False) as spk_acc:
                spk_conf_tb = gr.Textbox(
                    label="SeaTunnel config", lines=8, max_lines=8,
                    placeholder=t0("spk_conf_placeholder"),
                    show_label=False,
                )
                with gr.Row():
                    spk_btn = gr.Button(t0("spk_btn"), size="sm",
                                        variant="secondary")
                    spk_upload_btn = gr.UploadButton(
                        t0("dsk_upload_btn"), size="sm", scale=0, min_width=140,
                        file_types=[".conf", ".hocon", ".config", ".json", ".txt"])
                # appears after a check that measured a better split key:
                # the pasted config with the key already written in
                spk_apply_dl_btn = gr.DownloadButton(
                    t0("spk_apply_dl"), visible=False, size="sm")
            with gr.Accordion(t0("rt_accordion"), open=False) as rt_acc:
                with gr.Row():
                    rt_url_tb = gr.Textbox(
                        label=t0("rt_url"), placeholder="http://host:18080")
                    rt_app_tb = gr.Textbox(
                        label=t0("rt_app"), placeholder="application_…")
                with gr.Row():
                    rt_btn = gr.Button(t0("rt_btn"), size="sm",
                                       variant="secondary")
                    # event logs often have no extension — accept any file
                    rt_upload_btn = gr.UploadButton(
                        t0("rt_upload_btn"), size="sm", scale=0, min_width=170)
            with gr.Accordion(t0("dsk_history_accordion"),
                              open=False) as hist_acc:
                with gr.Row():
                    hist_dd = gr.Dropdown(choices=[], value=None,
                                          label=t0("dsk_history_pick"))
                    hist_refresh_btn = gr.Button(t0("dsk_history_refresh"),
                                                 size="sm", scale=0)
                    hist_load_btn = gr.Button(t0("dsk_history_load"),
                                              size="sm", scale=0)
                hist_md = gr.Markdown(t0("dsk_history_empty"))
        with gr.Column(scale=4):
            # dsk-report-card: the UI test agent reads/awaits this region
            report_md = gr.Markdown(t0("dsk_report_placeholder"),
                                    buttons=["copy"],
                                    elem_classes=["dsk-report-card"])
            with gr.Row():
                dl_report_btn = gr.DownloadButton(t0("dsk_download_report"),
                                                  visible=False, size="sm")
                dl_sql_btn = gr.DownloadButton(t0("dsk_download_sql"),
                                               visible=False, size="sm")
            optimized_box = gr.Code(label=t0("dsk_optimized_sql"),
                                    language="sql", visible=False,
                                    buttons=["copy"])

    def _tmp_file(name: str, content: str) -> str:
        path = Path(tempfile.mkdtemp(prefix="dataskew_")) / name
        path.write_text(content, encoding="utf-8")
        return str(path)

    # ── Optional datasource connection (skew verification) ──
    # Per-session gr.State: every browser session owns its connection and
    # probe cache — two sessions never share or clobber each other's
    # connection (the module-level holder the page started with did).

    conn_state = gr.State(None)   # {"executor", "ds_type", "status", "cache"}
    hist_state = gr.State([])     # records behind the history dropdown
    history = default_history()

    def _on_ds_change(ds: str):
        d = DS_DEFAULTS.get(ds, {})
        return (gr.update(placeholder=str(d.get("port", ""))),
                gr.update(placeholder=str(d.get("database", ""))))

    def do_connect(ds: str, host: str, port: str, db: str,
                   user: str, pwd: str, lang: str):
        defaults = DS_DEFAULTS.get(ds, {})
        host = (host or "").strip()
        db = (db or "").strip() or str(defaults.get("database", ""))
        try:
            if ds == "sqlite":
                cfg = DatabaseConfig(ds_type="sqlite", host="", port=0, database=db)
            elif not host:
                cfg = config_from_env(ds)
                if cfg is None:
                    raise RuntimeError(
                        "host is empty and no .env config found" if lang == "en"
                        else "主机为空且 .env 中未配置该数据源"
                    )
            else:
                try:
                    port_n = int((port or "").strip() or defaults.get("port", 0))
                except ValueError:
                    port_n = int(defaults.get("port", 0))
                cfg = DatabaseConfig(
                    ds_type=ds, host=host, port=port_n, database=db,
                    username=(user or "").strip() or None,
                    password=(pwd or "").strip() or None,
                )
            executor = create_executor(cfg)
            ok, info = executor.test_connection()
            if not ok:
                raise RuntimeError(info)
        except Exception as exc:  # noqa: BLE001 — surface in the UI
            return dsk(lang, "dsk_conn_fail").format(err=exc), None
        status = dsk(lang, "dsk_conn_ok").format(info=info)
        return status, {"executor": executor, "ds_type": ds,
                        "status": status, "cache": ProbeCache()}

    def _append_section(report_cur: str, section: str, head_re: re.Pattern[str]) -> str:
        """Replace/append one measured section on the current report."""
        report_cur = (report_cur or "").strip()
        placeholders = {dsk("zh", "dsk_report_placeholder"),
                        dsk("en", "dsk_report_placeholder")}
        if report_cur and report_cur not in placeholders:
            return _remove_section(report_cur, head_re) + "\n\n" + section
        return section

    def _restored_status(lang: str, conn: dict | None) -> str:
        return str((conn or {}).get("status") or "") or dsk(lang, "dsk_conn_status_none")

    def _cached_probes(conn: dict, sql: str, pct: int):
        """Probe results for (sql, datasource, sampling), reusing the last run."""
        cache: ProbeCache = conn["cache"]
        key = (sql, conn["ds_type"], pct)
        cached = cache.get(key)
        if cached is not None:
            return cached
        results = run_probes(conn["executor"], extract_probe_targets(sql),
                             ds_type=conn["ds_type"], sample_pct=pct)
        cache.put(key, results)
        return results

    def do_verify(sql: str, report_cur: str, dialect: str, sample: int,
                  lang: str, conn: dict | None):
        if not conn or conn.get("executor") is None:
            return gr.update(), dsk(lang, "dsk_verify_need_conn")
        sql = (sql or "").strip()
        if not sql:
            return gr.update(), dsk(lang, "dsk_empty_sql")
        pct = effective_sample_pct(conn["ds_type"], int(sample or 0))
        try:
            results = _cached_probes(conn, sql, pct)
            section = render_probe_section(
                results, lang, dialect=normalize_dialect(dialect), sample_pct=pct)
        except Exception as exc:  # noqa: BLE001 — surface in the UI
            return gr.update(), _err_md(exc, lang)
        history.log_verify(
            sql, targets=len(extract_probe_targets(sql)),
            confirmed=sum(1 for r in results if r.verdict == "confirmed"),
            source="ui")
        return (_append_section(report_cur, section, _PROBE_HEAD_RE),
                _restored_status(lang, conn))

    def do_consistency(sql: str, optimized: str, report_cur: str,
                       lang: str, conn: dict | None):
        if not conn or conn.get("executor") is None:
            return gr.update(), dsk(lang, "dsk_verify_need_conn")
        sql = (sql or "").strip()
        if not sql:
            return gr.update(), dsk(lang, "dsk_empty_sql")
        if not (optimized or "").strip():
            return gr.update(), dsk(lang, "cst_need_opt")
        try:
            res = check_consistency(conn["executor"], sql, optimized)
            section = render_consistency_section(res, lang)
        except Exception as exc:  # noqa: BLE001 — surface in the UI
            return gr.update(), _err_md(exc, lang)
        return (_append_section(report_cur, section, _CST_HEAD_RE),
                _restored_status(lang, conn))

    def _patched_conf_update(conf_text: str, results, total: int):
        """DownloadButton update: the pasted config with the measured best
        key written in — only for single-source configs where the best key
        differs from the configured one (mirrors the CLI --apply guard)."""
        hide = gr.update(visible=False)
        if total != 1:
            return hide
        spec, configured, candidates = results[0]
        best = pick_best_key(spec, configured, candidates)
        if best is None or best.column == spec.partition_column:
            return hide
        try:
            patched = apply_split_key(
                conf_text, spec, best.column,
                partition_num=max(spec.partition_num, spec.tasks))
        except SplitKeyError:
            return hide
        return gr.update(visible=True,
                         value=_tmp_file("seatunnel_patched.conf", patched))

    def do_splitkey(conf_text: str, report_cur: str, sample: int,
                    lang: str, conn: dict | None):
        hide = gr.update(visible=False)
        if not conn or conn.get("executor") is None:
            return gr.update(), dsk(lang, "spk_need_conn"), hide
        conf_text = (conf_text or "").strip()
        if not conf_text:
            return gr.update(), dsk(lang, "spk_empty_conf"), hide
        pct = effective_sample_pct(conn["ds_type"], int(sample or 0))
        try:
            results, total = run_split_key_multi(
                conn["executor"], conf_text,
                ds_type=conn["ds_type"], sample_pct=pct)
            # last checks of the same tables (fetched before logging this
            # run) render as the re-check comparison lines
            previous_by_table = {
                spec.table: prev for spec, _, _ in results
                if (prev := history.last_splitkey(spec.table))}
            section = render_splitkey_multi(
                results, lang, sample_pct=pct, total=total,
                previous_by_table=previous_by_table)
        except SplitKeyError as exc:
            return gr.update(), dsk(lang, exc.key).format(err=exc.arg), hide
        except Exception as exc:  # noqa: BLE001 — surface in the UI
            return gr.update(), _err_md(exc, lang), hide
        for spec, configured, candidates in results:
            history.log_splitkey(
                spec.table, spec.partition_column,
                configured.verdict(spec.tasks) if configured else "none",
                candidates=len(candidates), source="ui")
        return (_append_section(report_cur, section, _SPK_HEAD_RE),
                _restored_status(lang, conn),
                _patched_conf_update(conf_text, results, total))

    def _runtime_report(stages, label: str, report_cur: str, lang: str,
                        conn: dict | None):
        confirmed = sum(1 for s in stages if s.verdict() == "confirmed")
        suspect = sum(1 for s in stages if s.verdict() == "suspect")
        history.log_runtime(label, len(stages), confirmed, suspect,
                            source="ui")
        section = render_runtime_section(stages, lang, source_label=label)
        return (_append_section(report_cur, section, _RT_HEAD_RE),
                _restored_status(lang, conn))

    def do_runtime_file(path, report_cur: str, lang: str, conn: dict | None):
        if isinstance(path, (list, tuple)):
            path = path[0] if path else None
        if not path:
            return gr.update(), _restored_status(lang, conn)
        try:
            stages, label = parse_eventlog(str(path))
        except RuntimeSkewError as exc:
            return gr.update(), dsk(lang, exc.key).format(err=exc.arg)
        except Exception as exc:  # noqa: BLE001 — surface in the UI
            return gr.update(), _err_md(exc, lang)
        # the uploaded temp name is meaningless — label with the app name
        # from the log when it has one
        label = label if not str(label).startswith("tmp") else "event log"
        return _runtime_report(stages, label, report_cur, lang, conn)

    def do_runtime_history(url: str, app_id: str, report_cur: str,
                           lang: str, conn: dict | None):
        if not (url or "").strip() or not (app_id or "").strip():
            return gr.update(), dsk(lang, "rt_need_url")
        try:
            stages, label = analyze_history_server(url, app_id)
        except RuntimeSkewError as exc:
            return gr.update(), dsk(lang, exc.key).format(err=exc.arg)
        except Exception as exc:  # noqa: BLE001 — surface in the UI
            return gr.update(), _err_md(exc, lang)
        return _runtime_report(stages, label, report_cur, lang, conn)

    def _probe_for_llm(sql: str, lang: str, dialect: str, sample: int,
                       conn: dict | None) -> tuple[str, str]:
        """(prompt_context, report_section) from a connected datasource, or empties."""
        if not conn or conn.get("executor") is None:
            return "", ""
        if not extract_probe_targets(sql):
            return "", ""
        pct = effective_sample_pct(conn["ds_type"], int(sample or 0))
        try:
            results = _cached_probes(conn, sql, pct)
        except Exception:  # noqa: BLE001 — probing must never break the analysis
            return "", ""
        return (probe_lines_for_prompt(results, lang),
                render_probe_section(results, lang, dialect=dialect, sample_pct=pct))

    def do_analyze(sql: str, dialect: str, mode: str, sample: int,
                   lang: str, conn: dict | None):
        sql = (sql or "").strip()
        hide = gr.update(visible=False)
        if not sql:
            return dsk(lang, "dsk_empty_sql"), hide, hide, hide
        dialect = normalize_dialect(dialect)
        try:
            if mode == "static":
                rep = static_skew_report(sql, dialect, lang)
                report = render_report(rep, lang)
                optimized = ""
                history.log(sql, rep, mode="static", source="ui")
            else:
                try:
                    settings = load_settings()
                except RuntimeError:
                    rep = static_skew_report(sql, dialect, lang)
                    report = (dsk(lang, "dsk_llm_unavailable") + "\n\n"
                              + render_report(rep, lang))
                    history.log(sql, rep, mode="static", source="ui")
                    return (report,
                            gr.update(value=_tmp_file("data_skew_report.md", report),
                                      visible=True),
                            hide, hide)
                agent = DataSkewAgent(settings, dialect=dialect, lang=lang)
                out_path = Path(tempfile.mkdtemp(prefix="dataskew_")) / "my_task_optimized.sql"
                probe_ctx, probe_section = _probe_for_llm(sql, lang, dialect,
                                                          sample, conn)
                result = agent.analyze(sql, use_llm=True, output_path=out_path,
                                       probe_context=probe_ctx)
                report = result.markdown
                if probe_section:
                    report = report.rstrip() + "\n\n" + probe_section
                optimized = result.optimized_sql
                history.log(sql, result.report, mode="llm", source="ui")
        except Exception as exc:  # noqa: BLE001 — surface any failure in the UI
            return _err_md(exc, lang), hide, hide, hide

        dl_report = gr.update(value=_tmp_file("data_skew_report.md", report),
                              visible=True)
        if optimized:
            dl_sql = gr.update(value=_tmp_file("my_task_optimized.sql", optimized),
                               visible=True)
            opt_box = gr.update(value=optimized, visible=True)
        else:
            dl_sql, opt_box = hide, hide
        return report, dl_report, dl_sql, opt_box

    def _analyze_start(sql: str, mode: str, lang: str):
        if not (sql or "").strip():
            return gr.update(), gr.update()
        note = dsk(lang, "dsk_running_llm" if mode == "llm" else "dsk_running_static")
        return gr.update(value=f"⏳ {note}"), gr.update(interactive=False)

    analyze_btn.click(
        _analyze_start,
        inputs=[sql_box, mode_radio, lang_state],
        outputs=[report_md, analyze_btn],
    ).then(
        do_analyze,
        inputs=[sql_box, dialect_dd, mode_radio, sample_dd, lang_state,
                conn_state],
        outputs=[report_md, dl_report_btn, dl_sql_btn, optimized_box],
    ).then(
        lambda: gr.update(interactive=True),
        outputs=[analyze_btn],
    )

    def do_clear(lang: str):
        hide = gr.update(visible=False)
        return "", dsk(lang, "dsk_report_placeholder"), hide, hide, hide

    clear_btn.click(
        do_clear,
        inputs=[lang_state],
        outputs=[sql_box, report_md, dl_report_btn, dl_sql_btn, optimized_box],
    )

    # ── SQL file upload: fill the editor with the file's content ──

    def do_upload(path):
        if isinstance(path, (list, tuple)):
            path = path[0] if path else None
        if not path:
            return gr.update()
        try:
            text = Path(str(path)).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return gr.update()
        return gr.update(value=text[:200_000])

    upload_btn.upload(do_upload, inputs=[upload_btn], outputs=[sql_box])

    # ── Analysis history: refresh the list, reload a past analysis ──

    def _verdict_mark(rec: dict) -> str:
        c = rec.get("counts") or {}
        return f"⛔{c.get('high', 0)} ⚠️{c.get('medium', 0)} 🔵{c.get('low', 0)}"

    def _snippet(rec: dict, n: int) -> str:
        """One-line SQL snippet, safe inside a markdown-table code span
        ('|' would split the cell, a backtick would end the span)."""
        s = " ".join((rec.get("sql") or "").split())[:n]
        return s.replace("|", "\\|").replace("`", "'")

    def do_hist_refresh(lang: str):
        recs = history.recent(20)
        if not recs:
            return (gr.update(choices=[], value=None),
                    dsk(lang, "dsk_history_empty"), [])
        choices = []
        for i, r in enumerate(recs):
            snippet = " ".join((r.get("sql") or "").split())[:40]
            label = (f"{str(r.get('timestamp', ''))[5:16]} · "
                     f"{r.get('dialect', '')} · {_verdict_mark(r)} · {snippet}")
            choices.append((label, i))  # dropdown labels are plain text
        t = lambda k: dsk(lang, k)  # noqa: E731
        lines = [
            f"| {t('dsk_h_time')} | {t('dsk_h_source')} | {t('dsk_h_dialect')} "
            f"| {t('dsk_h_mode')} | {t('dsk_h_findings')} | {t('dsk_h_sql')} |",
            "|---|---|---|---|---|---|",
        ]
        for r in recs:
            lines.append(
                f"| {str(r.get('timestamp', ''))[:16]} | {r.get('source', '')} "
                f"| {r.get('dialect', '')} | {r.get('mode', '')} "
                f"| {_verdict_mark(r)} | `{_snippet(r, 60)}` |")
        return gr.update(choices=choices, value=0), "\n".join(lines), recs

    hist_refresh_btn.click(
        do_hist_refresh,
        inputs=[lang_state],
        outputs=[hist_dd, hist_md, hist_state],
    )

    def do_hist_load(idx, recs: list):
        if idx is None or not recs:
            return gr.update(), gr.update()
        try:
            rec = recs[int(idx)]
        except (ValueError, IndexError):
            return gr.update(), gr.update()
        return (gr.update(value=rec.get("sql") or ""),
                gr.update(value=normalize_dialect(rec.get("dialect") or "spark")))

    hist_load_btn.click(
        do_hist_load,
        inputs=[hist_dd, hist_state],
        outputs=[sql_box, dialect_dd],
    )

    # ── Saved connections (shared preset store with Settings / Data
    # Comparison): load names on demand, picking one fills the form ──

    def _presets_store():
        from .data_comparison.presets import ConnectionPresetsStore
        return ConnectionPresetsStore()

    def do_preset_load(lang: str):
        try:
            names = [p.get("name", "") for p in _presets_store().list()]
        except Exception:  # noqa: BLE001 — never break the page over the store
            names = []
        names = [n for n in names if n]
        if not names:
            return gr.update(choices=[], value=None), dsk(lang, "dsk_preset_none")
        return gr.update(choices=names, value=None), gr.update()

    preset_load_btn.click(
        do_preset_load,
        inputs=[lang_state],
        outputs=[preset_dd, conn_status],
    )

    def do_preset_pick(name: str | None, lang: str, conn: dict | None):
        no_change = tuple(gr.update() for _ in range(6)) + (gr.update(),)
        if not name:
            return no_change
        try:
            p = _presets_store().get_by_name(name)
        except Exception:  # noqa: BLE001
            p = None
        if not p:
            return no_change
        ds = str(p.get("ds_type") or "").lower()
        if ds not in _PROBE_DS:
            return (*tuple(gr.update() for _ in range(6)),
                    dsk(lang, "dsk_preset_unsupported").format(t=ds))
        return (gr.update(value=ds),
                gr.update(value=str(p.get("host") or "")),
                gr.update(value=str(p.get("port") or "")),
                gr.update(value=str(p.get("database") or "")),
                gr.update(value=str(p.get("username") or "")),
                gr.update(value=str(p.get("password") or "")),
                _restored_status(lang, conn))

    preset_dd.change(
        do_preset_pick,
        inputs=[preset_dd, lang_state, conn_state],
        outputs=[ds_dd, host_tb, port_tb, db_tb, user_tb, pwd_tb, conn_status],
    )

    ds_dd.change(_on_ds_change, inputs=[ds_dd], outputs=[port_tb, db_tb])

    connect_btn.click(
        do_connect,
        inputs=[ds_dd, host_tb, port_tb, db_tb, user_tb, pwd_tb, lang_state],
        outputs=[conn_status, conn_state],
    )

    verify_btn.click(
        lambda lang: gr.update(value=f"⏳ {dsk(lang, 'dsk_verify_running')}"),
        inputs=[lang_state],
        outputs=[conn_status],
    ).then(
        do_verify,
        inputs=[sql_box, report_md, dialect_dd, sample_dd, lang_state,
                conn_state],
        outputs=[report_md, conn_status],
    )

    cst_btn.click(
        lambda lang: gr.update(value=f"⏳ {dsk(lang, 'cst_running')}"),
        inputs=[lang_state],
        outputs=[conn_status],
    ).then(
        do_consistency,
        inputs=[sql_box, optimized_box, report_md, lang_state, conn_state],
        outputs=[report_md, conn_status],
    )

    spk_btn.click(
        lambda lang: gr.update(value=f"⏳ {dsk(lang, 'dsk_verify_running')}"),
        inputs=[lang_state],
        outputs=[conn_status],
    ).then(
        do_splitkey,
        inputs=[spk_conf_tb, report_md, sample_dd, lang_state, conn_state],
        outputs=[report_md, conn_status, spk_apply_dl_btn],
    )

    rt_btn.click(
        lambda lang: gr.update(value=f"⏳ {dsk(lang, 'rt_running')}"),
        inputs=[lang_state],
        outputs=[conn_status],
    ).then(
        do_runtime_history,
        inputs=[rt_url_tb, rt_app_tb, report_md, lang_state, conn_state],
        outputs=[report_md, conn_status],
    )

    rt_upload_btn.upload(
        do_runtime_file,
        inputs=[rt_upload_btn, report_md, lang_state, conn_state],
        outputs=[report_md, conn_status],
    )

    def do_conf_upload(path):
        if isinstance(path, (list, tuple)):
            path = path[0] if path else None
        if not path:
            return gr.update()
        try:
            text = Path(str(path)).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return gr.update()
        return gr.update(value=text[:200_000])

    spk_upload_btn.upload(do_conf_upload, inputs=[spk_upload_btn],
                          outputs=[spk_conf_tb])

    # Language switch — the returned tuple must stay positionally aligned
    # with the outputs list below.
    def _placeholder_update(current: str, key: str, lg: str):
        placeholders = {dsk("zh", key), dsk("en", key)}
        if (current or "").strip() in placeholders:
            return gr.update(value=dsk(lg, key))
        return gr.update()

    def _switch_lang(choice: str, report_cur: str, conn_cur: str,
                     hist_cur: str = ""):
        lg = "zh" if choice == "中文" else "en"
        t = lambda k: dsk(lg, k)  # noqa: E731
        return (
            lg,                                                    # lang_state
            f"{t('dsk_title')}\n{t('dsk_subtitle')}",              # title_md
            gr.update(placeholder=t("dsk_sql_placeholder")),       # sql_box
            gr.update(label=t("dsk_dialect")),                     # dialect_dd
            gr.update(label=t("dsk_mode"), choices=_mode_choices(lg)),  # mode_radio
            gr.update(value=t("dsk_analyze_btn")),                 # analyze_btn
            gr.update(value=t("dsk_clear_btn")),                   # clear_btn
            _placeholder_update(report_cur, "dsk_report_placeholder", lg),  # report_md
            gr.update(label=t("dsk_download_report")),             # dl_report_btn
            gr.update(label=t("dsk_download_sql")),                # dl_sql_btn
            gr.update(label=t("dsk_optimized_sql")),               # optimized_box
            gr.update(label=t("dsk_conn_accordion")),              # conn_acc
            gr.update(label=t("dsk_preset_dd")),                   # preset_dd
            gr.update(value=t("dsk_preset_load")),                 # preset_load_btn
            gr.update(label=t("dsk_ds_type")),                     # ds_dd
            gr.update(label=t("dsk_sample"),
                      choices=_sample_choices(lg)),                # sample_dd
            gr.update(label=t("dsk_host")),                        # host_tb
            gr.update(label=t("dsk_port")),                        # port_tb
            gr.update(label=t("dsk_db")),                          # db_tb
            gr.update(label=t("dsk_user")),                        # user_tb
            gr.update(label=t("dsk_pwd")),                         # pwd_tb
            gr.update(value=t("dsk_connect_btn")),                 # connect_btn
            gr.update(value=t("dsk_verify_btn")),                  # verify_btn
            gr.update(value=t("cst_btn")),                         # cst_btn
            _placeholder_update(conn_cur, "dsk_conn_status_none", lg),  # conn_status
            # UploadButton: value is the uploaded FILE — the text is `label`
            gr.update(label=t("dsk_upload_btn")),                  # upload_btn
            gr.update(label=t("spk_accordion")),                   # spk_acc
            gr.update(placeholder=t("spk_conf_placeholder")),      # spk_conf_tb
            gr.update(value=t("spk_btn")),                         # spk_btn
            gr.update(label=t("dsk_upload_btn")),                  # spk_upload_btn
            gr.update(label=t("spk_apply_dl")),                    # spk_apply_dl_btn
            gr.update(label=t("rt_accordion")),                    # rt_acc
            gr.update(label=t("rt_url")),                          # rt_url_tb
            gr.update(label=t("rt_app")),                          # rt_app_tb
            gr.update(value=t("rt_btn")),                          # rt_btn
            gr.update(label=t("rt_upload_btn")),                   # rt_upload_btn
            gr.update(label=t("dsk_history_accordion")),           # hist_acc
            gr.update(label=t("dsk_history_pick")),                # hist_dd
            gr.update(value=t("dsk_history_refresh")),             # hist_refresh_btn
            gr.update(value=t("dsk_history_load")),                # hist_load_btn
            _placeholder_update(hist_cur, "dsk_history_empty", lg),  # hist_md
        )

    from .lang_pref import HOME_JS, STAMP_JS, choice_from_request
    home_btn.click(fn=None, js=HOME_JS)
    # Language follows the hub's choice (st-lang cookie), applied on load.
    app.load(fn=None, js=STAMP_JS)

    def _lang_on_load(r, s, h, request: gr.Request):
        return _switch_lang(choice_from_request(request), r, s, h)

    app.load(
        _lang_on_load,
        inputs=[report_md, conn_status, hist_md],
        outputs=[
            lang_state, title_md, sql_box, dialect_dd, mode_radio,
            analyze_btn, clear_btn, report_md, dl_report_btn,
            dl_sql_btn, optimized_box,
            conn_acc, preset_dd, preset_load_btn,
            ds_dd, sample_dd, host_tb, port_tb, db_tb, user_tb, pwd_tb,
            connect_btn, verify_btn, cst_btn, conn_status,
            upload_btn, spk_acc, spk_conf_tb, spk_btn, spk_upload_btn,
            spk_apply_dl_btn,
            rt_acc, rt_url_tb, rt_app_tb, rt_btn, rt_upload_btn,
            hist_acc, hist_dd, hist_refresh_btn, hist_load_btn,
            hist_md,
        ],
    )
    # SQL handed over from the review page (localStorage bridge, same
    # mechanism as review → transpile): fill the box and fire an input
    # event so gradio picks the value up.
    app.load(fn=None, js="""
        () => setTimeout(() => {
            const v = localStorage.getItem('st_dataskew_sql');
            if (!v) return;
            const t = document.querySelector('#dsk-sql-box textarea');
            if (t) {
                // remove only after successful delivery: if the textarea
                // is not hydrated yet, the payload survives for a reload
                localStorage.removeItem('st_dataskew_sql');
                t.value = v;
                t.dispatchEvent(new Event('input', {bubbles: true}));
            }
        }, 600)""")

    # Connection handed over from Data Comparison (short-lived cookie set by
    # the skew card's goto button; no password travels): pre-fill the form
    # and open the accordion, the user adds the password and connects.
    def _conn_handoff_on_load(request: gr.Request):
        noop = tuple(gr.update() for _ in range(7))
        data = parse_conn_handoff(
            (request.cookies or {}).get(CONN_HANDOFF_COOKIE))
        if data is None:
            return noop
        from .lang_pref import choice_from_request
        lg = choice_from_request(request)
        if data["ds_type"] not in _PROBE_DS:
            return (*tuple(gr.update() for _ in range(6)),
                    dsk(lg, "dsk_conn_handoff_unsupported").format(
                        t=data["ds_type"] or "?"))
        return (
            gr.update(open=True),                    # conn_acc
            gr.update(value=data["ds_type"]),        # ds_dd
            gr.update(value=data["host"]),           # host_tb
            gr.update(value=data["port"]),           # port_tb
            gr.update(value=data["database"]),       # db_tb
            gr.update(value=data["username"]),       # user_tb
            dsk(lg, "dsk_conn_handoff").format(
                ds=data["ds_type"], host=data["host"],
                port=data["port"], db=data["database"]),  # conn_status
        )

    app.load(
        _conn_handoff_on_load,
        inputs=None,
        outputs=[conn_acc, ds_dd, host_tb, port_tb, db_tb, user_tb,
                 conn_status],
    )
