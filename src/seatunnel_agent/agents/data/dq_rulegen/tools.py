"""Chat/MCP tool entry point for the DQC rule drafter.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def dq_rulegen(sample: str, table: str, where: str = "",
               lang: str = "") -> str:
    """质量规则草稿生成（确定性）：粘贴表的样例数据（CSV 带表头或 JSONL）
    + 表名,按样例已做到的生成 DQC 可直接加载的 rules.yaml——row_count
    变化护栏、逐列空值率（观测值+5pp 余量）、主键形列 unique、低基数列
    enum_domain 钉观测值集。草稿经规则解析器回检。不连数据库。"""
    from seatunnel_agent.agents.data.dq_rulegen import (
        generate_rules,
        render_markdown,
    )
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    if not (sample or "").strip():
        return "样例不能为空 / sample must not be empty"
    if not (table or "").strip():
        return "表名不能为空 / table must not be empty"
    try:
        headers, rows = parse_rows(sample)
        draft = generate_rules(headers, rows, table, where=where)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(draft, lang=normalize_lang(lang))
