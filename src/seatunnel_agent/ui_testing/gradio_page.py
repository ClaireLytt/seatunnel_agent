"""Gradio page for the UI testing agent (route: /uitest).

Pick a suite (or case ids), run, watch streaming progress, view the report
inline and download it.  The run drives a *separate* app instance on port
7912+ — never the session serving this page.
"""

from __future__ import annotations

import html as _html
import queue
import threading
from pathlib import Path

import gradio as gr

_SUITES = ["smoke", "full", "sqlite", "hive", "slow"]

_I18N: dict[str, dict[str, str]] = {
    "en": {
        "title": "### UI Testing Agent",
        "subtitle": ("Browser-driven regression for the agent pages. The app "
                     "under test runs on its own port (7912+) and never "
                     "touches this session. Case docs: "
                     "`docs/ui_testing_usage.md`."),
        "suite": "Suite",
        "cases": "Specific cases (optional, space-separated, e.g. A5 B3; "
                 "overrides the suite)",
        "no_llm": "Skip LLM cases (0 tokens)",
        "run": "Run",
        "progress": "Progress",
        "download": "Download report",
        "starting": "Starting the app under test and seeding data…",
    },
    "zh": {
        "title": "### UI 测试 Agent",
        "subtitle": ("驱动真实浏览器回归各 Agent 页面。被测应用运行在独立端口 "
                     "7912+,不影响当前会话。用例文档见 "
                     "`docs/ui_testing_usage.md`。"),
        "suite": "套件",
        "cases": "指定用例 (可选,空格分隔,如 A5 B3;优先于套件)",
        "no_llm": "跳过 LLM 用例 (零 token)",
        "run": "运行",
        "progress": "进度",
        "download": "下载报告",
        "starting": "启动被测应用并种子数据…",
    },
}


def _ut(lang: str, key: str) -> str:
    return _I18N.get(lang, _I18N["en"]).get(key, key)


def _run_stream(suite: str, case_ids_text: str, no_llm: bool, lang: str):
    """Generator: streams progress lines, ends with the report."""
    from .report import print_summary, write_html, write_json  # noqa: F401
    from .runner import run_suite

    case_ids = [c for c in (case_ids_text or "").replace(",", " ").split()
                if c]
    q: queue.Queue = queue.Queue()
    done: dict = {}

    def progress(i, n, cr):
        q.put(f"[{i}/{n}] {cr.verdict:<6} {cr.case_id:<5} {cr.title} "
              f"({cr.elapsed_ms / 1000:.1f}s)")

    def work():
        try:
            rr, run_dir = run_suite(suite=suite, case_ids=case_ids or None,
                                    no_llm=no_llm, on_progress=progress)
            write_json(rr, run_dir)
            done["html"] = write_html(rr, run_dir)
            done["rr"] = rr
        except Exception as e:  # noqa: BLE001 — surfaced in the UI
            done["error"] = f"{type(e).__name__}: {e}"
        finally:
            q.put(None)

    t = threading.Thread(target=work, daemon=True)
    t.start()

    lines: list[str] = [_ut(lang, "starting")]
    yield "\n".join(lines), "", gr.update(visible=False)
    while True:
        item = q.get()
        if item is None:
            break
        lines.append(item)
        yield "\n".join(lines), "", gr.update(visible=False)
    t.join(timeout=10)

    if "error" in done:
        yield ("\n".join(lines) + f"\n\n❌ {done['error']}"), "", gr.update(visible=False)
        return

    rr = done["rr"]
    counts = rr.counts()
    elapsed = "耗时" if lang == "zh" else "elapsed"
    lines.append("")
    lines.append(f"PASS {counts['PASS']} · FAIL {counts['FAIL']} · "
                 f"ERROR {counts['ERROR']} · SKIP {counts['SKIP']} · "
                 f"MANUAL {counts['MANUAL']} · {elapsed} "
                 f"{rr.elapsed_ms / 1000:.0f}s")
    report_path: Path = done["html"]
    # embed the single-file report in a sandboxed iframe
    doc = report_path.read_text(encoding="utf-8")
    iframe = (f'<iframe style="width:100%;height:70vh;border:1px solid #e5e7eb;'
              f'border-radius:8px" srcdoc="{_html.escape(doc)}"></iframe>')
    yield ("\n".join(lines), iframe,
           gr.update(value=str(report_path), visible=True))


def render_uitest_page(app: gr.Blocks | None = None) -> None:
    t0 = lambda k: _ut("en", k)  # noqa: E731 — initial labels (default en)

    # marker: body:has(.st-uitest-page) re-enables page scrolling
    # (the global CSS locks .gradio-container to 100vh / overflow hidden)
    gr.HTML('<div class="st-uitest-page" style="display:none"></div>')
    with gr.Row():
        title_md = gr.Markdown(f"{t0('title')}\n{t0('subtitle')}")
        lang_dd = gr.Dropdown(
            choices=["English", "中文"], value="English",
            show_label=False, container=False, min_width=140, scale=0,
        )
    lang_state = gr.State("en")
    with gr.Row():
        suite_dd = gr.Dropdown(choices=_SUITES, value="smoke",
                               label=t0("suite"))
        case_tb = gr.Textbox(label=t0("cases"))
        no_llm_cb = gr.Checkbox(label=t0("no_llm"), value=True)
        run_btn = gr.Button(t0("run"), variant="primary")
    progress_tb = gr.Textbox(label=t0("progress"), lines=14,
                             interactive=False)
    report_html = gr.HTML()
    report_file = gr.DownloadButton(t0("download"), visible=False)

    def _switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        t = lambda k: _ut(lang, k)  # noqa: E731
        return (
            lang,
            f"{t('title')}\n{t('subtitle')}",
            gr.update(label=t("suite")),
            gr.update(label=t("cases")),
            gr.update(label=t("no_llm")),
            gr.update(value=t("run")),
            gr.update(label=t("progress")),
            gr.update(label=t("download")),
        )

    lang_dd.change(
        _switch_lang,
        inputs=[lang_dd],
        outputs=[lang_state, title_md, suite_dd, case_tb, no_llm_cb,
                 run_btn, progress_tb, report_file],
    )
    run_btn.click(fn=_run_stream,
                  inputs=[suite_dd, case_tb, no_llm_cb, lang_state],
                  outputs=[progress_tb, report_html, report_file])
