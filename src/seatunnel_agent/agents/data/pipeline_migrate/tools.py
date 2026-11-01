"""Chat/MCP tool entry point for the migration assessor agent.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def pipeline_migrate(scripts_dir: str = "", script: str = "",
                     lang: str = "") -> str:
    """Pipeline 迁移评估（确定性）：给出旧 ETL 脚本目录（递归扫 .sql/.hql/
    .sh/.py），或直接粘贴单个脚本，静态评估每个任务迁移到
    SeaTunnel/Spark/Flink 的落点：纯搬运 → SeaTunnel，批处理 SQL →
    Spark SQL，流式 → Flink，纯编排 shell → 留在调度器；按语句数、join、
    控制流与风险项透明打分出 S/M/L 工作量，并列出无法机械翻译的语法
    （UDF、存储过程、Oracle (+)、本地文件等）。只做静态分析，不执行。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.pipeline_migrate import (
        assess_dir,
        assess_text,
        render_markdown,
    )

    if not scripts_dir.strip() and not (script or "").strip():
        return ("请提供脚本目录或脚本内容 / "
                "provide scripts_dir or script text")
    try:
        if scripts_dir.strip():
            if not Path(scripts_dir.strip()).is_dir():
                return f"目录不存在 / not a directory: {scripts_dir.strip()}"
            result = assess_dir(scripts_dir.strip())
        else:
            result = assess_text("pasted.sql", script)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
