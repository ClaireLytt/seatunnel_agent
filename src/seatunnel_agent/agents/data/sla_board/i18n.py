"""EN/ZH strings for the SLA-board reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

SL_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "SLA Board",
        "rpt_scope": "**{tasks}** task(s), **{runs}** run(s) · overall "
                     "attainment **{rate:.1%}** vs target "
                     "**{target:.0%}** · ● {high} / ◐ {medium}",
        "rpt_clean": "Every task holds its deadline — the SLA stands.",
        "rpt_board": "Per-task attainment (worst first)",
        "col_task": "task",
        "col_runs": "runs",
        "col_rate": "rate",
        "col_p50": "p50 late",
        "col_p90": "p90 late",
        "col_streak": "live streak",
        "rpt_findings": "Findings",
        "col_sev": "sev",
        "col_code": "code",
        "col_issue": "issue",
        "SL001": "attainment {value:.1%} is below target",
        "SL002": "in a live miss streak of {value:g} day(s)",
        "SL003": "p90 lateness {value:g} min — chronically late",
        "min_suffix": "min",
        "rpt_disclaimer": "> Scored on the pasted records only — times "
                          "accept HH:MM (hours may pass 24 for "
                          "past-midnight finishes) or ISO datetimes. A "
                          "live streak means the misses have not "
                          "stopped; fix those tasks first.",
        "rpt_llm_note": "SLA review (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "SLA 达成看板",
        "rpt_scope": "**{tasks}** 个任务、**{runs}** 次运行 · 总达成率 "
                     "**{rate:.1%}**,目标 **{target:.0%}** · ● {high} / "
                     "◐ {medium}",
        "rpt_clean": "所有任务都守住了时限 — SLA 成立。",
        "rpt_board": "逐任务达成（最差在前）",
        "col_task": "任务",
        "col_runs": "次数",
        "col_rate": "达成率",
        "col_p50": "迟到 p50",
        "col_p90": "迟到 p90",
        "col_streak": "连续破线",
        "rpt_findings": "发现",
        "col_sev": "级",
        "col_code": "编码",
        "col_issue": "问题",
        "SL001": "达成率 {value:.1%} 低于目标",
        "SL002": "正处于连续 {value:g} 天破线中",
        "SL003": "迟到 p90 达 {value:g} 分钟 — 慢性迟到",
        "min_suffix": "分",
        "rpt_disclaimer": "> 仅就粘贴的记录打分 — 时间接受 HH:MM（过午夜"
                          "可写 25:30）或 ISO 时间。连续破线表示失约仍在"
                          "持续,这类任务优先修。",
        "rpt_llm_note": "SLA 评审（LLM — 发送前请复核）",
    },
}

tp = make_lookup(SL_I18N)
