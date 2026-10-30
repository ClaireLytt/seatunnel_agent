"""Chat/MCP tool entry point for the pipeline diagnosis agent.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def pipeline_diagnose(log_text: str, lang: str = "") -> str:
    """Pipeline 故障诊断（确定性）：粘贴 Spark/Hive/SeaTunnel 运行日志，
    识别引擎、匹配故障签名知识库（OOM/容器被杀/Metastore 失联/连接器缺失/
    配置解析/权限/Kerberos/磁盘配额等），给出首要嫌疑、根因与修复方案。
    不连库不调外部服务。"""
    from seatunnel_agent.agents.data.pipeline_doctor import (
        diagnose_text,
        render_markdown,
    )

    if not (log_text or "").strip():
        return "日志不能为空 / log text must not be empty"
    diag = diagnose_text(log_text)
    return render_markdown(diag, lang=normalize_lang(lang))
