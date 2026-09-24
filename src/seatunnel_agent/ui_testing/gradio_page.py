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


def _run_stream(suite: str, case_ids_text: str, no_llm: bool):
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

    lines: list[str] = ["启动被测应用并种子数据…"]
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
    lines.append("")
    lines.append(f"PASS {counts['PASS']} · FAIL {counts['FAIL']} · "
                 f"ERROR {counts['ERROR']} · SKIP {counts['SKIP']} · "
                 f"MANUAL {counts['MANUAL']} · 耗时 {rr.elapsed_ms / 1000:.0f}s")
    report_path: Path = done["html"]
    # embed the single-file report in a sandboxed iframe
    doc = report_path.read_text(encoding="utf-8")
    iframe = (f'<iframe style="width:100%;height:70vh;border:1px solid #e5e7eb;'
              f'border-radius:8px" srcdoc="{_html.escape(doc)}"></iframe>')
    yield ("\n".join(lines), iframe,
           gr.update(value=str(report_path), visible=True))


def render_uitest_page(app: gr.Blocks | None = None) -> None:
    gr.Markdown("### UI 测试 Agent")
    gr.Markdown("驱动真实浏览器回归数据对比页。被测应用运行在独立端口 7912+,"
                "不影响当前会话。用例文档见 `docs/ui_testing_usage.md`。")
    with gr.Row():
        suite_dd = gr.Dropdown(choices=_SUITES, value="smoke", label="套件")
        case_tb = gr.Textbox(label="指定用例 (可选,空格分隔,如 A5 B3;优先于套件)")
        no_llm_cb = gr.Checkbox(label="跳过 LLM 用例 (零 token)", value=True)
        run_btn = gr.Button("运行", variant="primary")
    progress_tb = gr.Textbox(label="进度", lines=14, interactive=False)
    report_html = gr.HTML()
    report_file = gr.DownloadButton("下载报告", visible=False)

    run_btn.click(fn=_run_stream, inputs=[suite_dd, case_tb, no_llm_cb],
                  outputs=[progress_tb, report_html, report_file])
