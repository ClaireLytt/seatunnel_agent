"""EN/ZH strings for sync-strategy reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

SYNC_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Sync Strategy Recommendation",
        "rpt_stats": ("tables {tables} · full {full} · timestamp incr "
                      "{incr_timestamp} · pk incr {incr_pk} · cdc {cdc}"),
        "rpt_col_table": "table",
        "rpt_col_strategy": "strategy",
        "rpt_col_reasons": "why",
        "rpt_col_risks": "risks",
        "strategy_full": "full reload",
        "strategy_incr_timestamp": "timestamp incremental",
        "strategy_incr_pk": "PK incremental",
        "strategy_cdc": "CDC",
        "reason_latency_needs_cdc": "minute-level latency and binlog available",
        "reason_deletes_without_cdc": "physical deletes, no CDC — "
                                      "incremental would miss them",
        "reason_small_table": "small table — full reload is cheap and "
                              "self-healing",
        "reason_high_churn": "over 30% of rows change daily — incremental "
                             "saves little",
        "reason_has_update_ts": "update-timestamp column available",
        "reason_pk_upsert": "primary key → idempotent upsert writes",
        "reason_pk_append_only": "primary key on an append-only table",
        "reason_no_incr_column": "no update timestamp or primary key to "
                                 "increment on",
        "risk_cdc_no_pk": "no primary key — CDC updates/deletes cannot be "
                          "applied idempotently",
        "risk_latency_without_cdc": "latency needs CDC but binlog is "
                                    "unavailable — enable it or relax the SLA",
        "risk_full_on_big_table": "full reload on a large table — watch "
                                  "window and source load",
        "risk_incr_no_pk_append_only": "no primary key — writes must be "
                                       "append-only, duplicates possible on retry",
        "risk_late_update_window": "rows updated later than the watermark "
                                   "are missed — keep an overlap window",
        "risk_pk_incr_misses_updates": "PK-based pull misses in-place "
                                       "updates — schedule periodic full compares",
        "rpt_disclaimer": ("> Deterministic rules over the declared table "
                           "characteristics — verify binlog grants, "
                           "watermark columns and write modes before "
                           "wiring the SeaTunnel job."),
    },
    "zh": {
        "rpt_title": "增量同步策略推荐",
        "rpt_stats": ("表 {tables} · 全量 {full} · 时间戳增量 "
                      "{incr_timestamp} · 主键增量 {incr_pk} · CDC {cdc}"),
        "rpt_col_table": "表",
        "rpt_col_strategy": "策略",
        "rpt_col_reasons": "理由",
        "rpt_col_risks": "风险",
        "strategy_full": "全量",
        "strategy_incr_timestamp": "时间戳增量",
        "strategy_incr_pk": "主键增量",
        "strategy_cdc": "CDC",
        "reason_latency_needs_cdc": "分钟级时延要求且 binlog 可用",
        "reason_deletes_without_cdc": "有物理删除且无 CDC — 增量会漏删",
        "reason_small_table": "小表 — 全量成本低且自愈",
        "reason_high_churn": "日变更超 30% — 增量省不了多少",
        "reason_has_update_ts": "有更新时间列",
        "reason_pk_upsert": "有主键 → 可幂等 upsert 写入",
        "reason_pk_append_only": "追加表且有主键",
        "reason_no_incr_column": "没有可用的更新时间列或主键",
        "risk_cdc_no_pk": "无主键 — CDC 的更新/删除无法幂等回放",
        "risk_latency_without_cdc": "时延要求需要 CDC 但 binlog 不可用 — "
                                    "开通 binlog 或放宽 SLA",
        "risk_full_on_big_table": "大表全量 — 注意窗口与源库压力",
        "risk_incr_no_pk_append_only": "无主键 — 只能追加写，重试可能产生重复",
        "risk_late_update_window": "晚于水位的更新会被漏掉 — 保留重叠窗口",
        "risk_pk_incr_misses_updates": "按主键拉取会漏掉原地更新 — "
                                       "需定期全量比对",
        "rpt_disclaimer": ("> 基于清单声明特征的确定性规则 — 接入 SeaTunnel "
                           "作业前请核实 binlog 权限、水位列与写入模式。"),
    },
}


tp = make_lookup(SYNC_I18N)
