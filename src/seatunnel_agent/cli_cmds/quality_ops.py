"""CLI entry points for the data-quality anomaly suite (36-41).

Thin wrappers over the deterministic cores, same conventions as
perf_ops.py (shared _read/_emit/fail_check):

  seatunnel-agent sampleprofile -f data.csv [--max-rows N --llm]
"""

from __future__ import annotations

import click

from .check_runner import emit_payload as _emit
from .check_runner import fail_check, report_options
from .check_runner import read_input as _read


@click.command("sampleprofile")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="CSV（带表头）或 JSONL 数据文件")
@click.option("--text", type=str, default=None, help="内联数据行")
@click.option("--max-rows", "max_rows", type=click.IntRange(min=1),
              default=2000, show_default=True,
              help="抽样上限：超过后做确定性等距抽样")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草数据体检通报（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级发现时 exit 1")
@report_options
def sampleprofile(path, text, max_rows, use_llm, fail_high,
                  lang, fmt, output) -> None:
    """数据抽样剖析 — CSV/JSONL → 列剖面 + 异常发现。"""
    from seatunnel_agent.agents.data.sample_profile import (
        parse_rows,
        profile_rows,
        render_markdown,
        sample_rows,
    )

    try:
        headers, rows = parse_rows(_read(path, text, "数据行"))
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    result = profile_rows(headers, sample_rows(rows, max_rows),
                          total_rows=len(rows))
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.sample_profile.advisor_llm import (
            review_note,
        )
        from seatunnel_agent.agents.data.sample_profile.i18n import tp

        note = review_note(result, lang=lang)
        payload["review_note"] = note
        markdown += f"\n\n### {tp(lang, 'rpt_llm_note')}\n{note}\n"
    _emit(payload, markdown, fmt, output)
    if fail_high:
        worst = [f for f in result.findings if f.severity == "high"]
        if worst:
            fail_check(
                "HIGH " + ", ".join(f"{f.code}:{f.column}" for f in worst),
                fmt)


def register(cli) -> None:
    cli.add_command(sampleprofile)
