"""EN/ZH strings for rerun plan reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

RERUN_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Rerun Plan",
        "rpt_stats": ("rerun {rerun} of {total} tasks · batches {batches} · "
                      "blast radius {radius}% · untouched {untouched}"),
        "rpt_eta": ("Estimated duration {total} (per batch: {batches} — "
                    "max within a batch, batches in sequence; task "
                    "durations default to 1)"),
        "rpt_steps": "Plan (run batches in order, tasks within a batch in parallel)",
        "rpt_col_batch": "batch",
        "rpt_col_task": "task",
        "rpt_col_reason": "reason",
        "rpt_col_from": "because of",
        "reason_failed": "failed",
        "reason_downstream": "stale inputs",
        "stale_note": " (had succeeded)",
        "rpt_commands": "Commands",
        "rpt_groups": "Independent recovery groups (no shared tasks — "
                      "recover in parallel)",
        "rpt_untouched": "Untouched branches",
        "rpt_unschedulable": "On a cycle (cannot be ordered)",
        "rpt_warnings": "Warnings",
        "rpt_disclaimer": ("> Deterministic plan — the rerun set is the "
                           "failed tasks plus their downstream closure; "
                           "upstream outputs are kept, siblings untouched. "
                           "Succeeded tasks inside the closure re-run anyway "
                           "(their inputs are stale). No scheduler "
                           "connection."),
    },
    "zh": {
        "rpt_title": "任务重跑计划",
        "rpt_stats": ("重跑 {rerun} / 共 {total} 个任务 · 批次 {batches} · "
                      "影响面 {radius}% · 不受影响 {untouched}"),
        "rpt_eta": ("预计耗时 {total}（各批次 {batches} — 批内取最大、"
                    "批间相加；任务时长缺省为 1）"),
        "rpt_steps": "计划（按批次顺序执行，同批次内可并行）",
        "rpt_col_batch": "批次",
        "rpt_col_task": "任务",
        "rpt_col_reason": "原因",
        "rpt_col_from": "起因",
        "reason_failed": "失败",
        "reason_downstream": "上游数据失效",
        "stale_note": "（曾成功）",
        "rpt_commands": "命令",
        "rpt_groups": "可独立恢复的分组（互不依赖 — 可并行恢复）",
        "rpt_untouched": "不受影响的分支",
        "rpt_unschedulable": "处于环上（无法排序）",
        "rpt_warnings": "警告",
        "rpt_disclaimer": ("> 确定性计划 — 重跑集合 = 失败任务 + 其下游闭包；"
                           "上游产出保留，兄弟分支不动。闭包内已成功的任务"
                           "因输入失效仍需重跑。不连调度器。"),
    },
}


tp = make_lookup(RERUN_I18N)
