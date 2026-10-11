# -*- coding: utf-8 -*-
"""Gradio page for the SeaTunnel config deep linter.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("Config Lint", "/conflint")``.  Fully deterministic — configs
are parsed against the built-in connector docs, never executed.
"""

from __future__ import annotations

import gradio as gr

from .config_lint import (
    lint_dir,
    lint_text,
    render_batch_markdown,
    render_markdown,
)
from .config_lint.i18n import normalize_lang

_I18N = {
    "en": {
        "title": "## 🧰 SeaTunnel Config Lint\n"
                 "Param-level lint against the built-in connector docs — "
                 "unknown connectors/params with did-you-mean suggestions, "
                 "missing required params, type & enum mismatches, CDC vs "
                 "job.mode sanity. Parsed, never executed.",
        "conf_label": "Config (HOCON)",
        "conf_ph": "Paste a SeaTunnel .conf…",
        "lint_btn": "Lint config",
        "dir_acc": "Lint a directory",
        "dir_label": "Config directory",
        "dir_ph": "Directory containing *.conf (scanned recursively), "
                  "e.g. examples/conflint_demo",
        "dir_btn": "Lint directory",
        "empty_conf": "⚠️ Paste a config first.",
        "empty_dir": "⚠️ Provide a config directory first.",
        "bad_dir": "⚠️ Not a directory: ",
    },
    "zh": {
        "title": "## 🧰 SeaTunnel 配置深度检查\n"
                 "基于内置连接器文档的参数级检查 — 未知连接器/参数带"
                 "「是不是想写」建议、缺失必填参数、类型与枚举校验、"
                 "CDC 与 job.mode 冲突检测。只解析不执行。",
        "conf_label": "配置 (HOCON)",
        "conf_ph": "粘贴 SeaTunnel .conf 配置…",
        "lint_btn": "检查配置",
        "dir_acc": "检查整个目录",
        "dir_label": "配置目录",
        "dir_ph": "包含 *.conf 的目录（递归扫描），如 examples/conflint_demo",
        "dir_btn": "检查目录",
        "empty_conf": "⚠️ 请先粘贴配置。",
        "empty_dir": "⚠️ 请先填写配置目录。",
        "bad_dir": "⚠️ 不是有效目录: ",
    },
}


def _t(lang: str, key: str) -> str:
    return _I18N[normalize_lang(lang)].get(key, key)


def render_config_lint_page(app: gr.Blocks) -> None:
    lang0 = "en"
    t = lambda k: _t(lang0, k)  # noqa: E731

    lang_state = gr.State(lang0)

    # marker: body:has(.st-scroll-page) re-enables page scrolling
    gr.HTML('<div class="st-scroll-page" style="display:none"></div>')

    with gr.Column(elem_classes=["st-cfl-page"]):
        with gr.Row():
            title_md = gr.Markdown(t("title"))
            home_btn = gr.Button("\U0001f3e0", size="sm", scale=0,
                                 elem_classes=["st-home-btn"])

        with gr.Row():
            with gr.Column(scale=2, elem_classes=["st-cfl-side"]):
                conf_box = gr.Textbox(
                    label=t("conf_label"), placeholder=t("conf_ph"),
                    lines=12)
                lint_btn = gr.Button(t("lint_btn"), variant="primary")
                with gr.Accordion(t("dir_acc"), open=False) as dir_acc:
                    dir_box = gr.Textbox(
                        label=t("dir_label"), placeholder=t("dir_ph"),
                        value="examples/conflint_demo")
                    dir_btn = gr.Button(t("dir_btn"))

            with gr.Column(scale=5, elem_classes=["st-cfl-main"]):
                report_md = gr.Markdown("")

    # ── callbacks ──

    def do_lint(conf_text: str, lang: str):
        lang = normalize_lang(lang)
        if not (conf_text or "").strip():
            return _t(lang, "empty_conf")
        try:
            return render_markdown(lint_text(conf_text), lang)
        except Exception as exc:  # noqa: BLE001 — lint must never crash the page
            return f"⚠️ {type(exc).__name__}: {exc}"

    def do_lint_dir(dir_text: str, lang: str):
        from pathlib import Path
        lang = normalize_lang(lang)
        if not (dir_text or "").strip():
            return _t(lang, "empty_dir")
        if not Path(dir_text.strip()).is_dir():
            return _t(lang, "bad_dir") + dir_text
        try:
            return render_batch_markdown(lint_dir(dir_text.strip()), lang)
        except Exception as exc:  # noqa: BLE001
            return f"⚠️ {type(exc).__name__}: {exc}"

    def switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        return (
            lang,
            gr.update(value=_t(lang, "title")),
            gr.update(label=_t(lang, "conf_label"),
                      placeholder=_t(lang, "conf_ph")),
            gr.update(value=_t(lang, "lint_btn")),
            gr.update(label=_t(lang, "dir_acc")),
            gr.update(label=_t(lang, "dir_label"),
                      placeholder=_t(lang, "dir_ph")),
            gr.update(value=_t(lang, "dir_btn")),
        )

    lint_btn.click(do_lint, inputs=[conf_box, lang_state],
                   outputs=[report_md])
    dir_btn.click(do_lint_dir, inputs=[dir_box, lang_state],
                  outputs=[report_md])

    from .lang_pref import HOME_JS, STAMP_JS, choice_from_request
    home_btn.click(fn=None, js=HOME_JS)
    app.load(fn=None, js=STAMP_JS)

    def _lang_on_load(request: gr.Request):
        return switch_lang(choice_from_request(request))

    app.load(
        _lang_on_load, inputs=None,
        outputs=[lang_state, title_md, conf_box, lint_btn, dir_acc,
                 dir_box, dir_btn],
    )
