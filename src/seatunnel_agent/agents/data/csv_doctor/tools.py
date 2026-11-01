"""Chat/MCP tool entry point for the CSV doctor.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def csv_doctor(data: str, lang: str = "") -> str:
    """CSV 急救（确定性）：粘贴喂不进去或一打开是乱码的 CSV 原文,字节取证
    + 结构修复——BOM/控制字符剥除、GBK/UTF-8 双重编码乱码复原（前后对照）、
    列数漂移行补齐或并入末列、表头重名加后缀、引号不配对与 U+FFFD 丢失
    点名;产出经本仓解析器回检的修复版 CSV。不连数据库。"""
    from seatunnel_agent.agents.data.csv_doctor import (
        diagnose_csv,
        render_markdown,
    )

    if not (data or "").strip():
        return "CSV 文本不能为空 / the CSV text must not be empty"
    try:
        report = diagnose_csv(data)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(report, lang=normalize_lang(lang))
