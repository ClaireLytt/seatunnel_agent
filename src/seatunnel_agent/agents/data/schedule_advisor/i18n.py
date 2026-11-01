"""EN/ZH strings for the schedule-advisor reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

SA_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Schedule Advice",
        "rpt_scope": "day starts {day_start} · SLA `{sla_task}` by "
                     "{deadline} · projected finish **{finish}**"
                     "{margin}",
        "rpt_margin_ok": " · margin **{m:g} min**",
        "rpt_margin_thin": " · margin **{m:g} min — THIN**",
        "rpt_margin_neg": " · margin **{m:g} min — MISSES THE SLA**",
        "rpt_critical": "Critical path (shorten these to move the "
                        "finish): {path}",
        "rpt_peak": "peak parallelism **{n}** task(s) at {at}",
        "rpt_tasks": "Timeline (earliest schedule)",
        "col_task": "task",
        "col_window": "start → finish",
        "col_duration": "min",
        "col_slack": "slack min",
        "col_critical": "critical",
        "yes": "yes",
        "rpt_movable": "Movable out of the peak (biggest slack first)",
        "movable_line": "- `{name}` can slip {slack_min:g} min without "
                        "moving the SLA task",
        "rpt_no_movable": "",
        "rpt_disclaimer": "> Deterministic earliest-schedule walk over "
                          "the declared durations and dependencies; "
                          "slack is relative to the SLA task. Durations "
                          "are your inputs — feed it p95 runtimes, not "
                          "averages, for safety margins.",
        "rpt_llm_note": "Schedule note (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "调度窗口建议",
        "rpt_scope": "起批 {day_start} · SLA `{sla_task}` 要求 "
                     "{deadline} 前 · 预计完成 **{finish}**{margin}",
        "rpt_margin_ok": " · 余量 **{m:g} 分钟**",
        "rpt_margin_thin": " · 余量 **{m:g} 分钟 — 偏薄**",
        "rpt_margin_neg": " · 余量 **{m:g} 分钟 — 将破线**",
        "rpt_critical": "关键路径（想提前完成只能缩短它们）：{path}",
        "rpt_peak": "并行峰值 **{n}** 个任务，出现在 {at}",
        "rpt_tasks": "时间线（最早排程）",
        "col_task": "任务",
        "col_window": "开始 → 完成",
        "col_duration": "分钟",
        "col_slack": "松弛分钟",
        "col_critical": "关键",
        "yes": "是",
        "rpt_movable": "可错峰任务（松弛大在前）",
        "movable_line": "- `{name}` 可后移 {slack_min:g} 分钟而不动 SLA "
                        "任务",
        "rpt_no_movable": "",
        "rpt_disclaimer": "> 按声明的时长与依赖做确定性最早排程；松弛"
                          "相对 SLA 任务计算。时长是你的输入 — 喂 p95 "
                          "而不是均值，余量才可靠。",
        "rpt_llm_note": "排程通报草稿（LLM — 发送前请复核）",
    },
}

tp = make_lookup(SA_I18N)
