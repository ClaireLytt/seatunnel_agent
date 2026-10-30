"""EN/ZH strings for backfill SQL reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

BACKFILL_SQL_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Backfill SQL",
        "rpt_stats": ("table `{table}` · mode {mode} · dialect {dialect} · "
                      "dates {dates} · statements {statements}"),
        "rpt_prechecks": "Pre-flight checks (run before backfilling)",
        "rpt_sql": "Backfill statements (one partition per block, "
                   "idempotent to re-run)",
        "rpt_date": "business date",
        "rpt_runner": "Runner script (stop-on-fail, one block at a time)",
        "rpt_postchecks": "Reconciliation (run after — lists only "
                          "mismatched partitions)",
        "rpt_warnings": "Warnings",
        "rpt_disclaimer": ("> Deterministic generation — every statement is "
                           "bounded to one partition via the {date} "
                           "placeholder, so re-running a block is safe. "
                           "The SQL is generated, never executed."),
    },
    "zh": {
        "rpt_title": "补数 SQL",
        "rpt_stats": ("表 `{table}` · 模式 {mode} · 方言 {dialect} · "
                      "日期 {dates} · 语句 {statements}"),
        "rpt_prechecks": "前置校验（补数前先跑）",
        "rpt_sql": "补数语句（每块只写一个分区，可安全重跑）",
        "rpt_date": "业务日期",
        "rpt_runner": "执行脚本（逐块执行，失败即停）",
        "rpt_postchecks": "对账（补数后跑 — 只列行数不一致的分区）",
        "rpt_warnings": "警告",
        "rpt_disclaimer": ("> 确定性生成 — 每条语句都通过 {date} 占位符"
                           "限定在单个分区内，重复执行安全。SQL 只生成，"
                           "不执行。"),
    },
}


tp = make_lookup(BACKFILL_SQL_I18N)
