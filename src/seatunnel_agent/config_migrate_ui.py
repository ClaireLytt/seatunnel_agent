# -*- coding: utf-8 -*-
"""Gradio page for the DataX/Sqoop → SeaTunnel migration agent.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("Config Migrate", "/migrate")``. Deterministic rule-based
conversion; everything unmappable becomes a visible note, never a silent
drop.
"""

from __future__ import annotations

import gradio as gr

_I18N = {
    "en": {
        "title": "## 🚚 DataX/Sqoop → SeaTunnel\n"
                 "Paste a DataX job JSON or a sqoop command line and get a "
                 "SeaTunnel config plus migration notes. Rule-based and "
                 "deterministic — no LLM, no database connection.",
        "job_label": "DataX job JSON / sqoop command",
        "job_ph": "Paste the DataX job json, or e.g. sqoop import --connect …",
        "migrate_btn": "Migrate",
        "batch_acc": "Batch migrate a directory",
        "dir_label": "Job directory",
        "dir_ph": "Directory with *.json / sqoop scripts (recursive)",
        "out_label": "Output directory (optional)",
        "out_ph": "Writes mirrored *.conf files when set",
        "batch_btn": "Batch migrate",
        "conf_label": "SeaTunnel config",
        "empty": "⚠️ Paste a DataX job or sqoop command first.",
        "bad_dir": "⚠️ Not a directory: ",
    },
    "zh": {
        "title": "## 🚚 DataX/Sqoop → SeaTunnel\n"
                 "粘贴 DataX job JSON 或 sqoop 命令行，得到 SeaTunnel 配置 + "
                 "迁移说明清单。规则驱动、确定性——不调用 LLM、不连接数据库。",
        "job_label": "DataX job JSON / sqoop 命令",
        "job_ph": "粘贴 DataX job json，或如 sqoop import --connect …",
        "migrate_btn": "迁移",
        "batch_acc": "批量迁移目录",
        "dir_label": "任务目录",
        "dir_ph": "包含 *.json / sqoop 脚本的目录（递归）",
        "out_label": "输出目录（可选）",
        "out_ph": "填写后按原结构写出 *.conf",
        "batch_btn": "批量迁移",
        "conf_label": "SeaTunnel 配置",
        "empty": "⚠️ 请先粘贴 DataX job 或 sqoop 命令。",
        "bad_dir": "⚠️ 不是有效目录: ",
    },
}


def _t(lang: str, key: str) -> str:
    lang = "en" if (lang or "").lower().startswith("en") else "zh"
    return _I18N[lang].get(key, key)


def render_config_migrate_page(app: gr.Blocks) -> None:
    lang0 = "en"
    t = lambda k: _t(lang0, k)  # noqa: E731

    lang_state = gr.State(lang0)

    with gr.Column(elem_classes=["st-mig-page"]):
        with gr.Row():
            title_md = gr.Markdown(t("title"))
            home_btn = gr.Button("\U0001f3e0", size="sm", scale=0,
                                 elem_classes=["st-home-btn"])

        with gr.Row():
            with gr.Column(scale=2, elem_classes=["st-mig-side"]):
                job_box = gr.Textbox(
                    label=t("job_label"), placeholder=t("job_ph"), lines=14)
                migrate_btn = gr.Button(t("migrate_btn"), variant="primary")
                with gr.Accordion(t("batch_acc"), open=False) as batch_acc:
                    dir_box = gr.Textbox(
                        label=t("dir_label"), placeholder=t("dir_ph"))
                    out_box = gr.Textbox(
                        label=t("out_label"), placeholder=t("out_ph"))
                    batch_btn = gr.Button(t("batch_btn"))

            with gr.Column(scale=5, elem_classes=["st-mig-main"]):
                conf_code = gr.Code(label=t("conf_label"), value="",
                                    language="yaml")
                report_md = gr.Markdown("")

    # ── callbacks ──

    def do_migrate(text: str, lang: str):
        from .config_migrate import migrate_text, render_migrate_markdown

        if not (text or "").strip():
            return "", _t(lang, "empty")
        res = migrate_text(text)
        return res.output_conf, render_migrate_markdown(res, lang)

    def do_batch(dir_text: str, out_text: str, lang: str):
        from pathlib import Path

        from .config_migrate import migrate_dir, render_batch_markdown

        if not (dir_text or "").strip():
            return "", _t(lang, "empty")
        if not Path(dir_text.strip()).is_dir():
            return "", _t(lang, "bad_dir") + dir_text
        try:
            batch = migrate_dir(dir_text.strip(),
                                out_dir=(out_text or "").strip() or None)
        except ValueError as exc:
            return "", f"⚠️ {exc}"
        return "", render_batch_markdown(batch, lang)

    def switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        return (
            lang,
            gr.update(value=_t(lang, "title")),
            gr.update(label=_t(lang, "job_label"),
                      placeholder=_t(lang, "job_ph")),
            gr.update(value=_t(lang, "migrate_btn")),
            gr.update(label=_t(lang, "batch_acc")),
            gr.update(label=_t(lang, "dir_label"),
                      placeholder=_t(lang, "dir_ph")),
            gr.update(label=_t(lang, "out_label"),
                      placeholder=_t(lang, "out_ph")),
            gr.update(value=_t(lang, "batch_btn")),
            gr.update(label=_t(lang, "conf_label")),
        )

    migrate_btn.click(do_migrate, inputs=[job_box, lang_state],
                      outputs=[conf_code, report_md])
    batch_btn.click(do_batch, inputs=[dir_box, out_box, lang_state],
                    outputs=[conf_code, report_md])
    from .lang_pref import HOME_JS, STAMP_JS, choice_from_request
    home_btn.click(fn=None, js=HOME_JS)
    # Language follows the hub's choice (st-lang cookie), applied on load.
    app.load(fn=None, js=STAMP_JS)

    def _lang_on_load(request: gr.Request):
        return switch_lang(choice_from_request(request))

    app.load(
        _lang_on_load, inputs=None,
        outputs=[lang_state, title_md, job_box, migrate_btn, batch_acc,
                 dir_box, out_box, batch_btn, conf_code],
    )
