"""EN/ZH strings for SLA trace reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

SLA_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Scheduling Delay Trace",
        "rpt_target": "target task",
        "rpt_stats": ("instances {instances} · critical path {steps} tasks · "
                      "end-to-end {total}"),
        "rpt_sla_ok": "SLA met: finished at {end}, {margin} before the {deadline} deadline",
        "rpt_sla_breach": "SLA BREACH: finished at {end}, {late} after the {deadline} deadline",
        "rpt_top": "Top delay contributors on the critical path",
        "rpt_col_task": "task",
        "rpt_col_wait": "waited",
        "rpt_col_run": "ran",
        "rpt_col_share": "share of path",
        "rpt_path": "Critical path (upstream to target)",
        "rpt_path_root": "run start",
        "rpt_path_step": "{name}: waited {wait} on {on}, ran {run}",
        "rpt_warnings": "Warnings",
        "rpt_disclaimer": ("> Deterministic trace — the critical path walks "
                           "from the target into whichever dependency "
                           "finished last (the one actually waited for); "
                           "no scheduler connection, exports only."),
    },
    "zh": {
        "rpt_title": "调度依赖延迟分析",
        "rpt_target": "目标任务",
        "rpt_stats": "任务实例 {instances} · 关键路径 {steps} 个任务 · 端到端 {total}",
        "rpt_sla_ok": "SLA 达标：{end} 完成，早于截止 {deadline} 共 {margin}",
        "rpt_sla_breach": "SLA 破线：{end} 完成，晚于截止 {deadline} 共 {late}",
        "rpt_top": "关键路径上的延迟大户",
        "rpt_col_task": "任务",
        "rpt_col_wait": "等待",
        "rpt_col_run": "运行",
        "rpt_col_share": "占路径比",
        "rpt_path": "关键路径（从上游到目标）",
        "rpt_path_root": "本轮起点",
        "rpt_path_step": "{name}：等 {on} 共 {wait}，运行 {run}",
        "rpt_warnings": "警告",
        "rpt_disclaimer": ("> 确定性分析 — 关键路径从目标任务逐级走向"
                           "实际等待的那个依赖（最后完成者）；"
                           "不连调度器，只读导出文件。"),
    },
}


tp = make_lookup(SLA_I18N)
