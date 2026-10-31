"""CLI entry points for the data-quality anomaly suite (36-41).

Thin wrappers over the deterministic cores, same conventions as
perf_ops.py (shared _read/_emit/fail_check):

  seatunnel-agent sampleprofile -f data.csv [--max-rows N --llm]
  seatunnel-agent distanomaly   --baseline base.csv --current cur.csv
  seatunnel-agent dupcheck      -f rows.csv [--pk id --biz-key "user,ts"]
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


@click.command("distanomaly")
@click.option("--baseline", "-b", "baseline_path",
              type=click.Path(exists=True, dir_okay=False), required=True,
              help="基线：CSV/JSONL 数据或 sampleprofile 的 profile JSON")
@click.option("--current", "-c", "current_path",
              type=click.Path(exists=True, dir_okay=False), required=True,
              help="当前：CSV/JSONL 数据或 profile JSON")
@click.option("--max-rows", "max_rows", type=click.IntRange(min=1),
              default=2000, show_default=True,
              help="剖析原始数据时每侧的抽样上限")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草漂移通报（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级漂移时 exit 1")
@report_options
def distanomaly(baseline_path, current_path, max_rows, use_llm, fail_high,
                lang, fmt, output) -> None:
    """数据分布异常 — 基线 vs 当前样本 → 漂移发现。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.dist_anomaly import (
        compare_profiles,
        load_profile,
        render_markdown,
    )

    def _load(path: str) -> dict:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        return load_profile(text, max_rows)

    try:
        result = compare_profiles(_load(baseline_path), _load(current_path))
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.dist_anomaly.advisor_llm import (
            drift_note,
        )
        from seatunnel_agent.agents.data.dist_anomaly.i18n import tp

        note = drift_note(result, lang=lang)
        payload["drift_note"] = note
        markdown += f"\n\n### {tp(lang, 'rpt_llm_note')}\n{note}\n"
    _emit(payload, markdown, fmt, output)
    if fail_high:
        worst = [f for f in result.findings if f.severity == "high"]
        if worst:
            fail_check(
                "HIGH " + ", ".join(f"{f.code}:{f.column}" for f in worst),
                fmt)


@click.command("dupcheck")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="CSV（带表头）或 JSONL 数据文件")
@click.option("--text", type=str, default=None, help="内联数据行")
@click.option("--pk", type=str, default="",
              help="主键列（逗号分隔），开启主键重复层")
@click.option("--biz-key", "biz_key", type=str, default="",
              help="业务键列（逗号分隔），开启业务事件重复层")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草去重处置通报（需配置 API key）")
@click.option("--fail-on-dup", "fail_dup", is_flag=True, default=False,
              help="CI gate：任何一层存在重复时 exit 1")
@report_options
def dupcheck(path, text, pk, biz_key, use_llm, fail_dup,
             lang, fmt, output) -> None:
    """数据重复检测 — 全行/主键/业务事件三层重复组。"""
    from seatunnel_agent.agents.data.dup_check import (
        detect_dups,
        render_markdown,
    )

    try:
        result = detect_dups(_read(path, text, "数据行"),
                             pk=pk or None, biz_key=biz_key or None)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.dup_check.advisor_llm import (
            dedup_note,
        )
        from seatunnel_agent.agents.data.dup_check.i18n import tp

        note = dedup_note(result, lang=lang)
        payload["dedup_note"] = note
        markdown += f"\n\n### {tp(lang, 'rpt_llm_note')}\n{note}\n"
    _emit(payload, markdown, fmt, output)
    if fail_dup:
        extra = result.row_dup_rows + result.pk_dup_rows + result.biz_dup_rows
        if extra:
            fail_check(f"DUPLICATES {extra} extra row(s)", fmt)


def register(cli) -> None:
    cli.add_command(sampleprofile)
    cli.add_command(distanomaly)
    cli.add_command(dupcheck)
