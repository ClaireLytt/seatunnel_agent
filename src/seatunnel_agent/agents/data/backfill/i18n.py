"""EN/ZH strings for backfill plan reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

BACKFILL_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Backfill Plan",
        "rpt_now": "evaluated at",
        "rpt_stats": ("impacted tables {tables} · batches {batches} · "
                      "slots to run {slots} · skipped {skipped}"),
        "rpt_steps": "Plan (run batches in order, tables within a batch in parallel)",
        "rpt_col_batch": "batch",
        "rpt_col_table": "table",
        "rpt_col_dates": "dates",
        "rpt_col_kind": "kind",
        "rpt_col_from": "because of",
        "kind_missing": "backfill",
        "kind_cascade": "re-run",
        "kind_both": "backfill + re-run",
        "not_in_inventory": " (not in inventory)",
        "rpt_commands": "Commands",
        "rpt_skipped": "Skipped tables",
        "skip_no_cadence": "fewer than 3 updates and no rule",
        "skip_cadence_too_fine": "cadence under 45m — calendar backfill not meaningful",
        "skip_no_updates_before_now": "no updates at or before the evaluated time",
        "rpt_warnings": "Warnings",
        "rpt_all_ok": "No missing partitions at the evaluated time — nothing to backfill.",
        "rpt_disclaimer": ("> Deterministic plan — gaps come from the "
                           "partition grid (rules or inferred cadence), the "
                           "cascade from the lineage's downstream closure; "
                           "'now' defaults to the latest update seen. "
                           "No database or scheduler connection."),
    },
    "zh": {
        "rpt_title": "补数计划",
        "rpt_now": "评估时刻",
        "rpt_stats": ("受影响表 {tables} · 批次 {batches} · "
                      "待跑分区 {slots} · 跳过 {skipped}"),
        "rpt_steps": "计划（按批次顺序执行，同批次内可并行）",
        "rpt_col_batch": "批次",
        "rpt_col_table": "表",
        "rpt_col_dates": "日期",
        "rpt_col_kind": "类型",
        "rpt_col_from": "起因",
        "kind_missing": "补数",
        "kind_cascade": "级联重跑",
        "kind_both": "补数 + 级联重跑",
        "not_in_inventory": "（不在清单中）",
        "rpt_commands": "命令",
        "rpt_skipped": "跳过的表",
        "skip_no_cadence": "更新不足 3 次且无规则",
        "skip_cadence_too_fine": "节奏小于 45 分钟，按日历补数无意义",
        "skip_no_updates_before_now": "评估时刻之前没有更新记录",
        "rpt_warnings": "警告",
        "rpt_all_ok": "评估时刻没有缺失分区，无需补数。",
        "rpt_disclaimer": ("> 确定性计划 — 缺口来自分区网格（规则或推断的节奏），"
                           "级联来自血缘的下游闭包；now 默认取清单里最晚的"
                           "更新时间。不连数据库，不连调度器。"),
    },
}


tp = make_lookup(BACKFILL_I18N)
