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
        "audit_title": "Layout audit (declared DDL vs workload)",
        "audit_col_code": "code",
        "audit_col_table": "table",
        "audit_col_detail": "detail",
        "audit_col_meaning": "what it means",
        "audit_ok": "The declared layout matches the workload.",
        "IA001": "the partition column is never equality-filtered by the "
                 "workload — pruning never kicks in",
        "IA002": "a different partition column fits the workload better "
                 "(declared -> recommended)",
        "IA003": "the hottest join key is not the bucketing column "
                 "(declared -> recommended)",
        "IA004": "the bucketing column has no join hits in the workload",
        "roi_title": "Partition ROI (estimated against the stats inventory)",
        "roi_none": "No partition recommendation to price, or the tables "
                    "are already partitioned as recommended.",
        "roi_col_saved": "workload scan saved",
        "roi_col_stmts": "statements estimated",
        "roi_skipped": "Not priced (missing from the inventory or "
                       "partition count < 2):",
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
        "audit_title": "现状审计（DDL 已声明布局 vs 负载）",
        "audit_col_code": "编号",
        "audit_col_table": "表",
        "audit_col_detail": "明细",
        "audit_col_meaning": "含义",
        "audit_ok": "已声明布局与负载匹配。",
        "IA001": "分区列在负载中从未被等值过滤 — 分区裁剪永远不生效",
        "IA002": "按负载另有更合适的分区列（已声明 -> 推荐）",
        "IA003": "最热 join key 不是分桶列（已声明 -> 推荐）",
        "IA004": "分桶列在负载中没有 join 命中",
        "roi_title": "分区建议 ROI（按统计清单估算）",
        "roi_none": "没有可定价的分区建议，或表已按建议分区。",
        "roi_col_saved": "整个负载省的扫描",
        "roi_col_stmts": "估算语句数",
        "roi_skipped": "未定价（清单缺失或分区数 < 2）：",
    },
}


tp = make_lookup(INDEX_I18N)
