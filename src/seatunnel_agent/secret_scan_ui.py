# -*- coding: utf-8 -*-
"""Gradio page for the secret scanner.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("Secret Scan", "/secretscan")``.  Deterministic and offline;
findings show masked previews only.
"""

from __future__ import annotations

import gradio as gr

from .secret_scan import ScanResult, render_markdown, scan_dir, scan_text
from .secret_scan.report import normalize_lang

_I18N = {
    "en": {
        "title": "## 🔑 Secret Scan\n"
                 "Find leaked credentials in code & config — provider tokens "
                 "(AWS / GitHub / Slack / Aliyun …), private keys, password "
                 "assignments, DSN-embedded passwords and high-entropy "
                 "strings. Previews are masked; placeholders are filtered. "
                 "CI gate: `seatunnel-agent secretscan --fail-on high`.",
        "text_label": "Text to scan",
        "text_ph": "Paste a config / env file / code snippet…",
        "scan_btn": "Scan",
        "dir_acc": "Scan a directory",
        "dir_label": "Directory",
        "dir_ph": "Scanned recursively (binaries & vendored dirs skipped), "
                  "e.g. examples/secretscan_demo",
        "dir_btn": "Scan directory",
        "report_ph": "▶ Findings appear here — severity, rule, file:line "
                     "and a masked preview.",
        "empty_text": "⚠️ Paste some text first.",
        "empty_dir": "⚠️ Provide a directory first.",
        "bad_dir": "⚠️ Not a directory: ",
    },
    "zh": {
        "title": "## 🔑 敏感凭证扫描\n"
                 "找出代码与配置里的泄漏凭证 — 云厂商 token(AWS / GitHub / "
                 "Slack / 阿里云…)、私钥块、明文密码赋值、DSN 内嵌密码与"
                 "高熵字符串。预览已脱敏,占位符自动过滤。CI 门禁:"
                 "`seatunnel-agent secretscan --fail-on high`。",
        "text_label": "待扫描文本",
        "text_ph": "粘贴配置 / env 文件 / 代码片段…",
        "scan_btn": "扫描",
        "dir_acc": "扫描目录",
        "dir_label": "目录",
        "dir_ph": "递归扫描(跳过二进制与依赖目录),如 "
                  "examples/secretscan_demo",
        "dir_btn": "扫描目录",
        "report_ph": "▶ 扫描后在此显示结果 — 严重度、规则、文件:行号与"
                     "脱敏预览。",
        "empty_text": "⚠️ 请先粘贴文本。",
        "empty_dir": "⚠️ 请先填写目录。",
        "bad_dir": "⚠️ 不是有效目录: ",
    },
}


def _t(lang: str, key: str) -> str:
    return _I18N[normalize_lang(lang)].get(key, key)


def render_secret_scan_page(app: gr.Blocks) -> None:
    lang0 = "en"
    t = lambda k: _t(lang0, k)  # noqa: E731

    lang_state = gr.State(lang0)

    # marker: body:has(.st-scroll-page) re-enables page scrolling
    gr.HTML('<div class="st-scroll-page" style="display:none"></div>')

    with gr.Column(elem_classes=["st-fmt-page"]):
        with gr.Row():
            title_md = gr.Markdown(t("title"))
            home_btn = gr.Button("\U0001f3e0", size="sm", scale=0,
                                 elem_classes=["st-home-btn"])

        with gr.Row():
            with gr.Column(scale=2, elem_classes=["st-fmt-side"]):
                text_box = gr.Textbox(label=t("text_label"),
                                      placeholder=t("text_ph"), lines=12)
                scan_btn = gr.Button(t("scan_btn"), variant="primary")
                with gr.Accordion(t("dir_acc"), open=False) as dir_acc:
                    dir_box = gr.Textbox(label=t("dir_label"),
                                         placeholder=t("dir_ph"),
                                         value="examples/secretscan_demo")
                    dir_btn = gr.Button(t("dir_btn"))

            with gr.Column(scale=5, elem_classes=["st-fmt-main"]):
                report_md = gr.Markdown(t("report_ph"))

    # ── callbacks ──

    def do_scan_text(text: str, lang: str):
        lang = normalize_lang(lang)
        if not (text or "").strip():
            return _t(lang, "empty_text")
        try:
            result = ScanResult(findings=scan_text(text), files_scanned=1)
            return render_markdown(result, lang)
        except Exception as exc:  # noqa: BLE001 — never crash the page
            return f"⚠️ {type(exc).__name__}: {exc}"

    def do_scan_dir(dir_text: str, lang: str):
        from pathlib import Path
        lang = normalize_lang(lang)
        if not (dir_text or "").strip():
            return _t(lang, "empty_dir")
        if not Path(dir_text.strip()).is_dir():
            return _t(lang, "bad_dir") + dir_text
        try:
            return render_markdown(scan_dir(dir_text.strip()), lang)
        except Exception as exc:  # noqa: BLE001
            return f"⚠️ {type(exc).__name__}: {exc}"

    def switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        return (
            lang,
            gr.update(value=_t(lang, "title")),
            gr.update(label=_t(lang, "text_label"),
                      placeholder=_t(lang, "text_ph")),
            gr.update(value=_t(lang, "scan_btn")),
            gr.update(label=_t(lang, "dir_acc")),
            gr.update(label=_t(lang, "dir_label"),
                      placeholder=_t(lang, "dir_ph")),
            gr.update(value=_t(lang, "dir_btn")),
        )

    scan_btn.click(do_scan_text, inputs=[text_box, lang_state],
                   outputs=[report_md])
    dir_btn.click(do_scan_dir, inputs=[dir_box, lang_state],
                  outputs=[report_md])

    from .lang_pref import HOME_JS, STAMP_JS, choice_from_request
    home_btn.click(fn=None, js=HOME_JS)
    app.load(fn=None, js=STAMP_JS)

    def _lang_on_load(current_report: str, request: gr.Request):
        lang_tuple = switch_lang(choice_from_request(request))
        placeholders = {_t("zh", "report_ph"), _t("en", "report_ph"), ""}
        rep_upd = (gr.update(value=_t(lang_tuple[0], "report_ph"))
                   if (current_report or "").strip() in placeholders
                   else gr.update())
        return (*lang_tuple, rep_upd)

    app.load(
        _lang_on_load, inputs=[report_md],
        outputs=[lang_state, title_md, text_box, scan_btn, dir_acc,
                 dir_box, dir_btn, report_md],
    )
