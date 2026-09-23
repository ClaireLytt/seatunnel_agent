"""Gradio page for the Data Skew agent.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("Data Skew", "/dataskew")``. Static mode is pure local rule
scanning; LLM mode also rewrites the SQL following the fixed 5-step
workflow. The page is bilingual (EN/ZH) following the same switch pattern
as the SQL Review / Data Comparison pages.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import gradio as gr

from .config import load_settings
from .data_skew.agent import DataSkewAgent, static_skew_check
from .data_skew.detector import DIALECTS, normalize_dialect
from .data_skew.i18n import dsk

_DIALECT_LABELS = {
    "spark": "Spark SQL (Spark 3)",
    "maxcompute": "MaxCompute SQL",
    "hive": "Hive SQL",
}
_DIALECT_CHOICES = [(_DIALECT_LABELS[d], d) for d in DIALECTS]

_DEFAULT_LANG = "en"


def _mode_choices(lang: str) -> list[tuple[str, str]]:
    return [(dsk(lang, "dsk_mode_static"), "static"),
            (dsk(lang, "dsk_mode_llm"), "llm")]


def _err_md(exc: Exception, lang: str) -> str:
    sep = ": " if lang == "en" else "："
    return f"❌ **{dsk(lang, 'dsk_error')}**{sep}{exc}"


def render_data_skew_page(app: gr.Blocks) -> None:
    t0 = lambda k: dsk(_DEFAULT_LANG, k)  # noqa: E731 — initial labels

    # marker: body:has(.st-skew-page) re-enables page scrolling
    gr.HTML('<div class="st-skew-page st-review-page" style="display:none"></div>')

    with gr.Row():
        title_md = gr.Markdown(f"{t0('dsk_title')}\n{t0('dsk_subtitle')}")
        lang_dd = gr.Dropdown(
            choices=["English", "中文"], value="English",
            show_label=False, container=False, min_width=140, scale=0,
        )
    lang_state = gr.State(_DEFAULT_LANG)

    with gr.Row():
        with gr.Column(scale=3):
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
                clear_btn = gr.Button(t0("dsk_clear_btn"), scale=0, min_width=80)
        with gr.Column(scale=4):
            report_md = gr.Markdown(t0("dsk_report_placeholder"),
                                    buttons=["copy"])
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

    def do_analyze(sql: str, dialect: str, mode: str, lang: str):
        sql = (sql or "").strip()
        hide = gr.update(visible=False)
        if not sql:
            return dsk(lang, "dsk_empty_sql"), hide, hide, hide
        dialect = normalize_dialect(dialect)
        try:
            if mode == "static":
                report = static_skew_check(sql, dialect, lang)
                optimized = ""
            else:
                try:
                    settings = load_settings()
                except RuntimeError:
                    report = (dsk(lang, "dsk_llm_unavailable") + "\n\n"
                              + static_skew_check(sql, dialect, lang))
                    return (report,
                            gr.update(value=_tmp_file("data_skew_report.md", report),
                                      visible=True),
                            hide, hide)
                agent = DataSkewAgent(settings, dialect=dialect, lang=lang)
                out_path = Path(tempfile.mkdtemp(prefix="dataskew_")) / "my_task_optimized.sql"
                result = agent.analyze(sql, use_llm=True, output_path=out_path)
                report = result.markdown
                optimized = result.optimized_sql
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
        inputs=[sql_box, dialect_dd, mode_radio, lang_state],
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

    # Language switch — the returned tuple must stay positionally aligned
    # with the outputs list below.
    def _placeholder_update(current: str, key: str, lg: str):
        placeholders = {dsk("zh", key), dsk("en", key)}
        if (current or "").strip() in placeholders:
            return gr.update(value=dsk(lg, key))
        return gr.update()

    def _switch_lang(choice: str, report_cur: str):
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
        )

    lang_dd.change(
        _switch_lang,
        inputs=[lang_dd, report_md],
        outputs=[
            lang_state, title_md, sql_box, dialect_dd, mode_radio,
            analyze_btn, clear_btn, report_md, dl_report_btn,
            dl_sql_btn, optimized_box,
        ],
    )
