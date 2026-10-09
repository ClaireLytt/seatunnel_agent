# -*- coding: utf-8 -*-
"""Gradio page for the whole-database sync generator.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("SyncGen", "/syncgen")``. Offline only — paste a MySQL DDL
snapshot, get per-table SeaTunnel configs + target DDL + a manifest.
Deterministic, no LLM, no DB connection.
"""

from __future__ import annotations

import gradio as gr

from .sync_gen import SyncPlan, generate_sync, render_markdown
from .sync_gen.i18n import normalize_lang

_I18N = {
    "en": {
        "title": "## 🚚 Whole-Database Sync Generator\n"
                 "Paste a MySQL DDL snapshot and batch-generate one "
                 "SeaTunnel sync config per table, the target-side CREATE "
                 "TABLE DDL (Doris/StarRocks/Hive type mapping), and "
                 "optional PII masking transforms. Deterministic, no LLM; "
                 "configs use ${var} placeholders instead of credentials.",
        "ddl_label": "MySQL DDL script (CREATE TABLE ...)",
        "sink_label": "Sink type",
        "include_label": "Include regex (optional)",
        "exclude_label": "Exclude regex (optional)",
        "pii_label": "Inject PII masking",
        "strategy_label": "Masking strategy",
        "run_btn": "Generate",
        "table_label": "Preview table",
        "conf_label": "SeaTunnel config",
        "ddl_out_label": "Target CREATE TABLE",
        "empty_ddl": "⚠️ Paste some CREATE TABLE statements first.",
    },
    "zh": {
        "title": "## 🚚 全库同步生成器\n"
                 "粘贴 MySQL 库的 DDL 快照，批量生成每张表的 SeaTunnel "
                 "同步配置 + 目标端建表语句（Doris/StarRocks/Hive 类型映射），"
                 "可选注入 PII 脱敏 transform。确定性、无 LLM；"
                 "配置用 ${var} 占位符，不含真实凭据。",
        "ddl_label": "MySQL DDL 脚本（CREATE TABLE ...）",
        "sink_label": "目标端类型",
        "include_label": "Include 正则（可选）",
        "exclude_label": "Exclude 正则（可选）",
        "pii_label": "注入 PII 脱敏",
        "strategy_label": "脱敏策略",
        "run_btn": "生成",
        "table_label": "预览表",
        "conf_label": "SeaTunnel 配置",
        "ddl_out_label": "目标端建表语句",
        "empty_ddl": "⚠️ 请先粘贴 CREATE TABLE 语句。",
    },
}

_DEMO_DDL = """\
CREATE TABLE shop.users (
  id BIGINT UNSIGNED NOT NULL,
  user_name VARCHAR(64) COMMENT '用户昵称',
  phone VARCHAR(20) COMMENT '手机号',
  email VARCHAR(128) COMMENT '电子邮件地址',
  amount DECIMAL(12,2) COMMENT '累计消费',
  status ENUM('active','frozen') COMMENT '账户状态',
  created_at DATETIME NOT NULL COMMENT '注册时间',
  PRIMARY KEY (id)
) COMMENT='用户表';
"""

_SINKS = ["console", "doris", "starrocks", "hive"]


def _t(lang: str, key: str) -> str:
    return _I18N[normalize_lang(lang)].get(key, key)


def render_sync_gen_page(app: gr.Blocks) -> None:
    lang0 = "en"
    t = lambda k: _t(lang0, k)  # noqa: E731

    lang_state = gr.State(lang0)
    files_state = gr.State({})   # {table_full_name: (conf, ddl)}

    # marker: body:has(.st-scroll-page) re-enables page scrolling
    gr.HTML('<div class="st-scroll-page" style="display:none"></div>')

    with gr.Column(elem_classes=["st-syncgen-page"]):
        with gr.Row():
            title_md = gr.Markdown(t("title"))
            home_btn = gr.Button("\U0001f3e0", size="sm", scale=0,
                                 elem_classes=["st-home-btn"])

        with gr.Row():
            with gr.Column(scale=2, elem_classes=["st-syncgen-side"]):
                ddl_box = gr.Textbox(label=t("ddl_label"), value=_DEMO_DDL,
                                     lines=14)
                sink_dd = gr.Dropdown(choices=_SINKS, value="starrocks",
                                      label=t("sink_label"))
                include_box = gr.Textbox(label=t("include_label"), value="")
                exclude_box = gr.Textbox(label=t("exclude_label"), value="")
                pii_cb = gr.Checkbox(label=t("pii_label"), value=True)
                strategy_rd = gr.Radio(choices=["md5", "mask"], value="md5",
                                       label=t("strategy_label"))
                run_btn = gr.Button(t("run_btn"), variant="primary")

            with gr.Column(scale=5, elem_classes=["st-syncgen-main"]):
                report_md = gr.Markdown("")
                table_dd = gr.Dropdown(choices=[], value=None,
                                       label=t("table_label"), visible=False)
                conf_code = gr.Code(label=t("conf_label"), language="python",
                                    visible=False)
                ddl_code = gr.Code(label=t("ddl_out_label"), language="sql",
                                   visible=False)

    # ── callbacks ──

    def do_generate(ddl: str, sink: str, include: str, exclude: str,
                    pii: bool, strategy: str, lang: str):
        lang = normalize_lang(lang)
        hidden = (gr.update(visible=False),) * 3
        if not (ddl or "").strip():
            return (_t(lang, "empty_ddl"), {}) + hidden
        plan = SyncPlan(
            source_mode="ddl", ddl_text=ddl, sink_type=sink,
            include=(include or "").strip() or None,
            exclude=(exclude or "").strip() or None,
            pii=bool(pii), pii_strategy=strategy)
        try:
            result = generate_sync(plan)
        except Exception as exc:  # noqa: BLE001 — generation must never crash the page
            return (f"⚠️ {type(exc).__name__}: {exc}", {}) + hidden
        files = {t_.spec.full_name: (t_.config_text, t_.ddl_text or "")
                 for t_ in result.tables}
        names = list(files)
        first = names[0] if names else None
        conf0, ddl0 = files.get(first, ("", "")) if first else ("", "")
        return (
            render_markdown(result, lang),
            files,
            gr.update(choices=names, value=first, visible=bool(names)),
            gr.update(value=conf0, visible=bool(names)),
            gr.update(value=ddl0, visible=bool(names and ddl0)),
        )

    def pick_table(name: str, files: dict):
        conf, ddl = files.get(name, ("", ""))
        return gr.update(value=conf), gr.update(value=ddl, visible=bool(ddl))

    run_btn.click(
        do_generate,
        inputs=[ddl_box, sink_dd, include_box, exclude_box, pii_cb,
                strategy_rd, lang_state],
        outputs=[report_md, files_state, table_dd, conf_code, ddl_code],
    )
    table_dd.change(pick_table, inputs=[table_dd, files_state],
                    outputs=[conf_code, ddl_code])

    from .lang_pref import HOME_JS, STAMP_JS, choice_from_request
    home_btn.click(fn=None, js=HOME_JS)
    app.load(fn=None, js=STAMP_JS)

    def switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        return (
            lang,
            gr.update(value=_t(lang, "title")),
            gr.update(label=_t(lang, "ddl_label")),
            gr.update(label=_t(lang, "sink_label")),
            gr.update(label=_t(lang, "include_label")),
            gr.update(label=_t(lang, "exclude_label")),
            gr.update(label=_t(lang, "pii_label")),
            gr.update(label=_t(lang, "strategy_label")),
            gr.update(value=_t(lang, "run_btn")),
            gr.update(label=_t(lang, "table_label")),
            gr.update(label=_t(lang, "conf_label")),
            gr.update(label=_t(lang, "ddl_out_label")),
        )

    def _lang_on_load(request: gr.Request):
        return switch_lang(choice_from_request(request))

    app.load(
        _lang_on_load, inputs=None,
        outputs=[lang_state, title_md, ddl_box, sink_dd, include_box,
                 exclude_box, pii_cb, strategy_rd, run_btn, table_dd,
                 conf_code, ddl_code],
    )
