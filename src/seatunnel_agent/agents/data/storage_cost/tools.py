"""Chat/MCP tool entry point for the storage-cost analyzer.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def storage_cost(inventory: str, partitions: str = "",
                 retention_days: int = 365, lang: str = "") -> str:
    """存储成本治理（确定性）：粘贴资产清单（CSV/JSON：table,size_gb,
    access_cnt_30d,last_access,downstream_cnt,可选 avg_file_mb），可选再
    贴分区明细（table,partition,size_gb）；输出按收益排序的动作 — 迁冷
    （>=100GB、30 天零访问且 >90 天未动）、清理超保留期的日期分区、
    平均文件 <16MB 的小文件合并，每条附证据与预计释放 GB。不连数据库。"""
    from seatunnel_agent.agents.data.storage_cost import (
        render_markdown,
        run_storage_analysis,
    )

    if not (inventory or "").strip():
        return "资产清单不能为空 / inventory must not be empty"
    try:
        result = run_storage_analysis(inventory, partitions_text=partitions,
                                      retention_days=retention_days)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    except Exception as exc:  # malformed CSV/JSON
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
