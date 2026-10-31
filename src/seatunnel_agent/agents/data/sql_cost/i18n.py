"""EN/ZH strings for SQL cost cards."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

SQLCOST_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "SQL Cost Card",
        "rpt_stats": ("scan {scan} · shuffle {shuffle} · output ~{rows} "
                      "rows · {core_s} core-seconds"),
        "rpt_verdict": ("Suggested parallelism **{par}** → wall clock "
                        "roughly **{lo} ~ {hi}** · peak task memory "
                        "~{mem}"),
        "rpt_scans": "Scans",
        "rpt_col_table": "table",
        "rpt_col_bytes": "scanned",
        "rpt_col_rows": "rows",
        "rpt_col_pruned": "partition pruned",
        "rpt_col_colratio": "column ratio",
        "yes": "yes",
        "no": "NO",
        "rpt_missing": "Tables missing from the stats inventory "
                       "(excluded from the totals)",
        "rpt_assumptions": "Assumptions",
        "asm_lines": ("per-core throughput 100 MB/s · broadcast threshold "
                      "10 MB · GROUP BY shrink x10 · shuffle partitions "
                      "200 · memory headroom x3 · uncertainty 0.5x–2x"),
        "wi_title": "What-if",
        "wi_scan": "scan {before} -> {after} (saves {pct}%)",
        "wi_no_save": ("> No saving: the SQL has no equality filter on "
                       "that column, so partition pruning never kicks in."),
        "rpt_disclaimer": ("> Order-of-magnitude estimate from the declared "
                           "stats — validate against a real run before "
                           "capacity decisions. No database connection."),
        "cmp_title": "Rewrite comparison (original vs rewritten SQL)",
        "cmp_col_axis": "axis",
        "cmp_col_base": "original",
        "cmp_col_rewrite": "rewritten",
        "cmp_col_saved": "saved",
        "cmp_scan": "scan",
        "cmp_shuffle": "shuffle",
        "cmp_memory": "peak task memory",
        "cmp_core": "core-seconds",
        "cmp_worse": "> The rewrite is MORE expensive on the axes marked "
                     "negative — re-check it before shipping.",
        "bat_title": "Workload cost ranking (most expensive first)",
        "bat_col_query": "query",
        "bat_col_scan": "scan",
        "bat_col_shuffle": "shuffle",
        "bat_col_core": "core-seconds",
        "bat_total": "total ({n})",
        "bat_skipped": "Not estimated (unparseable):",
        "cal_title": "Calibration (estimate vs the real run)",
        "cal_col_axis": "axis",
        "cal_col_est": "estimated",
        "cal_col_act": "actual",
        "cal_col_ratio": "actual / estimated",
        "cal_duration": "duration",
        "cal_scan_bytes": "scan",
        "cal_shuffle_bytes": "shuffle",
        "cal_in_band": "The run landed inside the stated 0.5x-2x band.",
        "cal_off_band": ("> The run fell outside the stated band "
                         "({lo} ~ {hi}) — apply the duration ratio as a "
                         "correction factor for this workload."),
    },
    "zh": {
        "rpt_title": "SQL 代价卡",
        "rpt_stats": ("扫描 {scan} · shuffle {shuffle} · 输出约 {rows} 行 · "
                      "{core_s} 核·秒"),
        "rpt_verdict": ("建议并行度 **{par}** → 预计耗时约 **{lo} ~ {hi}** · "
                        "任务内存峰值约 {mem}"),
        "rpt_scans": "扫描明细",
        "rpt_col_table": "表",
        "rpt_col_bytes": "扫描量",
        "rpt_col_rows": "行数",
        "rpt_col_pruned": "分区裁剪",
        "rpt_col_colratio": "列裁剪比",
        "yes": "是",
        "no": "否",
        "rpt_missing": "统计清单缺失的表（未计入总量）",
        "rpt_assumptions": "假设",
        "asm_lines": ("单核吞吐 100 MB/s · 广播阈值 10 MB · GROUP BY 收缩 "
                      "x10 · shuffle 分区 200 · 内存安全系数 x3 · "
                      "不确定区间 0.5x–2x"),
        "wi_title": "What-if",
        "wi_scan": "扫描 {before} → {after}（省 {pct}%）",
        "wi_no_save": "> 没省：SQL 未对该列做等值过滤，分区裁剪不生效。",
        "rpt_disclaimer": ("> 基于声明统计的量级估算 — 容量决策前请用真实"
                           "运行校准。不连数据库。"),
        "cmp_title": "改写省比（原 SQL vs 改写 SQL）",
        "cmp_col_axis": "维度",
        "cmp_col_base": "原 SQL",
        "cmp_col_rewrite": "改写后",
        "cmp_col_saved": "省",
        "cmp_scan": "扫描",
        "cmp_shuffle": "shuffle",
        "cmp_memory": "任务内存峰值",
        "cmp_core": "核·秒",
        "cmp_worse": "> 标负号的维度改写反而更贵 — 上线前再核对一遍。",
        "bat_title": "负载代价排行（最贵在前）",
        "bat_col_query": "查询",
        "bat_col_scan": "扫描",
        "bat_col_shuffle": "shuffle",
        "bat_col_core": "核·秒",
        "bat_total": "合计（{n}）",
        "bat_skipped": "未估算（无法解析）：",
        "cal_title": "校准（预估 vs 实跑）",
        "cal_col_axis": "维度",
        "cal_col_est": "预估",
        "cal_col_act": "实跑",
        "cal_col_ratio": "实跑 / 预估",
        "cal_duration": "耗时",
        "cal_scan_bytes": "扫描",
        "cal_shuffle_bytes": "shuffle",
        "cal_in_band": "实跑落在声明的 0.5x–2x 区间内。",
        "cal_off_band": ("> 实跑超出声明区间（{lo} ~ {hi}）— 该负载后续估算"
                         "可按耗时倍率折算。"),
    },
}


tp = make_lookup(SQLCOST_I18N)
