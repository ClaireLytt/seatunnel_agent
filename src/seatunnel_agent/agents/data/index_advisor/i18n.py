"""EN/ZH strings for index-advisor reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

INDEX_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Index / Partition Recommendation",
        "rpt_stats": ("statements {statements} · tables {tables} · "
                      "skipped {skipped}"),
        "rpt_table_head": "table",
        "rpt_col_part": "partition",
        "rpt_col_bucket": "bucketing",
        "rpt_col_index": "composite index",
        "rpt_col_stmts": "statements",
        "rpt_hot_cols": "Hot columns (eq / range / join / group hits)",
        "rpt_ddl": "DDL fragments (adapt and apply)",
        "rpt_skipped": "Skipped statements (not parseable)",
        "none_mark": "-",
        "rpt_disclaimer": ("> Deterministic counts over the parsed workload "
                           "— frequencies say what the queries want, not "
                           "what the data allows; check cardinality before "
                           "applying. No database connection."),
    },
    "zh": {
        "rpt_title": "索引 / 分区推荐",
        "rpt_stats": "语句 {statements} · 表 {tables} · 跳过 {skipped}",
        "rpt_table_head": "表",
        "rpt_col_part": "分区列",
        "rpt_col_bucket": "分桶列",
        "rpt_col_index": "组合索引",
        "rpt_col_stmts": "命中语句",
        "rpt_hot_cols": "热点列（等值 / 范围 / join / group 次数）",
        "rpt_ddl": "DDL 片段（按需调整后应用）",
        "rpt_skipped": "跳过的语句（无法解析）",
        "none_mark": "-",
        "rpt_disclaimer": ("> 对已解析工作负载的确定性计数 — 频次反映查询"
                           "想要什么，不代表数据允许什么；应用前请核对基数。"
                           "不连数据库。"),
    },
}


tp = make_lookup(INDEX_I18N)
