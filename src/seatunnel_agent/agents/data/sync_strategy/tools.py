"""Chat/MCP tool entry point for the sync-strategy agent.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def sync_strategy(tables: str, lang: str = "") -> str:
    """增量同步策略推荐（确定性）：粘贴源表更新特征清单（JSON 列表或带
    表头的 CSV，字段 table/rows/daily_change_rows/has_update_ts/has_pk/
    has_deletes/cdc_available/latency），按规则逐表推荐 全量 / 时间戳增量 /
    主键增量 / CDC，并给出理由与剩余风险（漏删、晚到更新、无主键等）。
    不连数据库。"""
    from seatunnel_agent.agents.data.sync_strategy import (
        parse_tables,
        recommend,
        render_markdown,
    )

    if not (tables or "").strip():
        return "表特征清单不能为空 / table inventory must not be empty"
    try:
        result = recommend(parse_tables(tables))
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    except Exception as exc:  # json errors etc.
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
