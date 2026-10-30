"""EN/ZH strings for execution-plan analysis reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

SQLPERF_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Execution Plan Analysis",
        "rpt_stats": ("joins {joins} · shuffles {exchanges} · scans "
                      "{scans} · findings {high} high / {medium} medium / "
                      "{info} info"),
        "rpt_findings": "Findings",
        "rpt_col_code": "code",
        "rpt_col_severity": "severity",
        "rpt_col_detail": "where",
        "rpt_col_advice": "what to do",
        "PF001": "cartesian / nested-loop join — add the missing join "
                 "condition or an explicit broadcast",
        "PF002": "scan reads every partition (PartitionFilters is empty) "
                 "— add the partition predicate",
        "PF003": "filter did not push down to the scan — move the "
                 "predicate onto base columns (no functions/casts on "
                 "the filtered column)",
        "PF004": "more shuffles than the joins explain — align join/"
                 "group keys or pre-bucket the tables to reuse "
                 "partitioning",
        "PF005": "SortMergeJoin in the plan — if one side is small, "
                 "broadcast it (hint or autoBroadcastJoinThreshold)",
        "PF006": "wide scan — select only the needed columns so the "
                 "reader can prune",
        "rpt_scans": "Scans",
        "rpt_col_table": "table",
        "rpt_col_cols": "columns read",
        "rpt_col_part": "partition filters",
        "rpt_col_pushed": "pushed filters",
        "not_stated": "(not stated)",
        "empty_mark": "EMPTY",
        "rpt_all_ok": "No findings — the plan looks tight.",
        "rpt_disclaimer": ("> Deterministic read of the EXPLAIN text — "
                           "the findings reflect what the engine planned, "
                           "not runtime metrics. No engine connection."),
    },
    "zh": {
        "rpt_title": "执行计划分析",
        "rpt_stats": ("join {joins} · shuffle {exchanges} · 扫描 {scans} · "
                      "发现 高{high} / 中{medium} / 提示{info}"),
        "rpt_findings": "发现",
        "rpt_col_code": "编号",
        "rpt_col_severity": "级别",
        "rpt_col_detail": "位置",
        "rpt_col_advice": "处方",
        "PF001": "笛卡尔积/嵌套循环 join — 补上缺失的关联条件，或显式广播小表",
        "PF002": "扫描读了全部分区（PartitionFilters 为空）— 补分区谓词",
        "PF003": "过滤没有下推到扫描 — 谓词改写到裸列上（过滤列别套函数/转型）",
        "PF004": "shuffle 数量超出 join 所需 — 对齐 join/group key 或预分桶复用分区",
        "PF005": "计划里有 SortMergeJoin — 小表侧可广播（hint 或调大 "
                 "autoBroadcastJoinThreshold）",
        "PF006": "宽表扫描 — 只选需要的列让读取器裁剪",
        "rpt_scans": "扫描明细",
        "rpt_col_table": "表",
        "rpt_col_cols": "读取列数",
        "rpt_col_part": "分区过滤",
        "rpt_col_pushed": "下推过滤",
        "not_stated": "（计划未标注）",
        "empty_mark": "空",
        "rpt_all_ok": "没有发现问题 — 这个计划看起来很紧凑。",
        "rpt_disclaimer": ("> 对 EXPLAIN 文本的确定性解读 — 发现反映引擎的"
                           "计划决策，不是运行期指标。不连引擎。"),
    },
}


tp = make_lookup(SQLPERF_I18N)
