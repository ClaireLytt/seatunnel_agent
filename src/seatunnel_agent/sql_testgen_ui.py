# -*- coding: utf-8 -*-
"""Gradio page for the SQL test-data generator.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("Test Data", "/testgen")``.  Fully deterministic — no external
database, no LLM; optional validation runs on in-memory SQLite (stdlib).
"""

from __future__ import annotations

import gradio as gr

from .sql_testgen import generate, render_markdown, validate_with_sqlite
from .sql_testgen.i18n import normalize_lang

_DIALECTS = ["hive", "spark", "mysql", "postgresql", "clickhouse",
             "doris", "starrocks"]

_DEMO_SQL = """SELECT u.user_id, u.user_name, sum(o.amount) AS pay_amount
FROM dwd.user_info u
JOIN dwd.order_pay o ON u.user_id = o.user_id
WHERE o.dt = '2024-01-01' AND o.status IN ('PAID', 'DONE')
GROUP BY u.user_id, u.user_name"""

_I18N = {
    "en": {
        "title": "## 🧪 SQL Test Data Generator\n"
                 "Generate minimal per-table datasets that actually exercise "
                 "a query: equi-join columns share value pools, WHERE "
                 "literals are satisfied, boundary rows (NULL/zero/empty) "
                 "are mixed in — then optionally execute everything on "
                 "in-memory SQLite. No external database.",
        "sql_label": "Query SQL",
        "sql_ph": "Paste the SELECT / INSERT...SELECT to generate data for…",
        "ddl_label": "DDL (optional)",
        "ddl_ph": "CREATE TABLE statements for exact column types…",
        "dialect_label": "SQL dialect",
        "rows_label": "Rows per table",
        "validate_label": "Validate on SQLite",
        "gen_btn": "Generate",
        "empty_sql": "⚠️ Paste a query first.",
    },
    "zh": {
        "title": "## 🧪 SQL 测试数据生成\n"
                 "为查询生成最小可用的测试数据集：关联列共享取值池、WHERE "
                 "字面量被满足、混入边界行（NULL/零值/空串）——并可选在内存 "
                 "SQLite 上执行整条链路验证。不依赖外部数据库。",
        "sql_label": "查询 SQL",
        "sql_ph": "粘贴需要造数的 SELECT / INSERT...SELECT…",
        "ddl_label": "DDL（可选）",
        "ddl_ph": "粘贴 CREATE TABLE 以获得精确的列类型…",
        "dialect_label": "SQL 方言",
        "rows_label": "每表行数",
        "validate_label": "SQLite 验证",
        "gen_btn": "生成测试数据",
        "empty_sql": "⚠️ 请先粘贴查询 SQL。",
    },
}


def _t(lang: str, key: str) -> str:
    return _I18N[normalize_lang(lang)].get(key, key)


def render_sql_testgen_page(app: gr.Blocks) -> None:
    lang0 = "en"
    t = lambda k: _t(lang0, k)  # noqa: E731

    lang_state = gr.State(lang0)

    # marker: body:has(.st-scroll-page) re-enables page scrolling
    gr.HTML('<div class="st-scroll-page" style="display:none"></div>')

    with gr.Column(elem_classes=["st-tgn-page"]):
        with gr.Row():
            title_md = gr.Markdown(t("title"))
            home_btn = gr.Button("\U0001f3e0", size="sm", scale=0,
                                 elem_classes=["st-home-btn"])

        with gr.Row():
            with gr.Column(scale=2, elem_classes=["st-tgn-side"]):
                sql_box = gr.Textbox(
                    label=t("sql_label"), placeholder=t("sql_ph"),
                    value=_DEMO_SQL, lines=8)
                ddl_box = gr.Textbox(
                    label=t("ddl_label"), placeholder=t("ddl_ph"), lines=5)
                dialect_dd = gr.Dropdown(
                    choices=_DIALECTS, value="hive",
                    label=t("dialect_label"))
                rows_slider = gr.Slider(
                    minimum=1, maximum=50, value=5, step=1,
                    label=t("rows_label"))
                validate_cb = gr.Checkbox(value=True,
                                          label=t("validate_label"))
                gen_btn = gr.Button(t("gen_btn"), variant="primary")

            with gr.Column(scale=5, elem_classes=["st-tgn-main"]):
                report_md = gr.Markdown("")

    # ── callbacks ──

    def do_generate(sql: str, ddl: str, dialect: str, rows: float,
                    do_validate: bool, lang: str):
        lang = normalize_lang(lang)
        if not (sql or "").strip():
            return _t(lang, "empty_sql")
        try:
            result = generate(sql, ddl=ddl or "", rows=int(rows),
                              dialect=dialect)
            if do_validate and result.tables:
                result.validation = validate_with_sqlite(result)
        except Exception as exc:  # noqa: BLE001 — generation must never crash the page
            return f"⚠️ {type(exc).__name__}: {exc}"
        return render_markdown(result, lang)

    def switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        return (
            lang,
            gr.update(value=_t(lang, "title")),
            gr.update(label=_t(lang, "sql_label"),
                      placeholder=_t(lang, "sql_ph")),
            gr.update(label=_t(lang, "ddl_label"),
                      placeholder=_t(lang, "ddl_ph")),
            gr.update(label=_t(lang, "dialect_label")),
            gr.update(label=_t(lang, "rows_label")),
            gr.update(label=_t(lang, "validate_label")),
            gr.update(value=_t(lang, "gen_btn")),
        )

    gen_btn.click(
        do_generate,
        inputs=[sql_box, ddl_box, dialect_dd, rows_slider, validate_cb,
                lang_state],
        outputs=[report_md],
    )

    from .lang_pref import HOME_JS, STAMP_JS, choice_from_request
    home_btn.click(fn=None, js=HOME_JS)
    app.load(fn=None, js=STAMP_JS)

    def _lang_on_load(request: gr.Request):
        return switch_lang(choice_from_request(request))

    app.load(
        _lang_on_load, inputs=None,
        outputs=[lang_state, title_md, sql_box, ddl_box, dialect_dd,
                 rows_slider, validate_cb, gen_btn],
    )
