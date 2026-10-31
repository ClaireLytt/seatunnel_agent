"""EN/ZH strings for DAG conflict reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

DAGCONFLICT_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Concurrent DAG Conflicts",
        "rpt_stats": ("capacity {cap_slots} slots / {cap_mem} GB · peak "
                      "demand {peak_slots} slots / {peak_mem} GB · "
                      "over-capacity windows {windows} · write conflicts "
                      "{writes}"),
        "rpt_windows": "Over-capacity windows",
        "rpt_col_window": "window",
        "rpt_col_peak": "peak (slots / GB)",
        "rpt_col_tasks": "tasks running",
        "rpt_writes": "Write-write conflicts (different DAGs, same table, "
                      "overlapping runs)",
        "rpt_suggestion": ("**Stagger suggestion** — delay `{dag}` by "
                           "**{delay}**: peak {before} → {after} slots, "
                           "{windows_after} window(s) left (re-simulated, "
                           "not assumed)."),
        "rpt_all_ok": "No over-capacity windows and no write conflicts — "
                      "the schedules coexist.",
        "rpt_disclaimer": ("> ASAP schedule per DAG from the declared "
                           "durations and resources — a what-if timeline, "
                           "not scheduler telemetry. No scheduler "
                           "connection."),
        "plc_title": "Admission check for `{dag}`",
        "plc_best": ("Best start offset **{offset}**: {windows} window(s), "
                     "{writes} write conflict(s), peak {peak} slots "
                     "(declared offset {declared_offset}: "
                     "{declared_windows} / {declared_writes} / "
                     "{declared_peak}). Every candidate re-simulated."),
        "plc_keep": "The declared offset is already among the best.",
        "plc_col_offset": "offset",
        "plc_col_windows": "windows",
        "plc_col_writes": "write conflicts",
        "plc_col_peak": "peak slots",
        "plc_candidates": "Candidate offsets (boundaries of the other "
                          "DAGs' runs)",
        "rpt_deadlines": "Deadline misses",
        "rpt_deadline_row": "`{dag}` finishes at {finish} — deadline "
                            "{deadline} (late by {late})",
        "rpt_suggestion_breaks": (" **Caution**: this delay pushes "
                                  "`{dag}` past its deadline "
                                  "({finish} > {deadline}) — stagger a "
                                  "different DAG or raise capacity."),
    },
    "zh": {
        "rpt_title": "多 DAG 并发冲突",
        "rpt_stats": ("容量 {cap_slots} 槽 / {cap_mem} GB · 峰值需求 "
                      "{peak_slots} 槽 / {peak_mem} GB · 超容时间窗 "
                      "{windows} · 写写冲突 {writes}"),
        "rpt_windows": "超容时间窗",
        "rpt_col_window": "时间窗",
        "rpt_col_peak": "峰值（槽 / GB）",
        "rpt_col_tasks": "同时在跑",
        "rpt_writes": "写写冲突（不同 DAG、同一张表、运行区间重叠）",
        "rpt_suggestion": ("**错峰建议** — 将 `{dag}` 顺延 **{delay}**：峰值 "
                           "{before} → {after} 槽，剩余超容窗 "
                           "{windows_after} 个（已重新模拟验证，非估计）。"),
        "rpt_all_ok": "没有超容时间窗，也没有写写冲突 — 这些调度可以共存。",
        "rpt_disclaimer": ("> 按声明的时长与资源做各 DAG 的 ASAP 时间线推演 "
                           "— what-if 模拟，不是调度器遥测。不连调度器。"),
        "plc_title": "`{dag}` 准入检查",
        "plc_best": ("最优起点 **{offset}**：超容窗 {windows} 个、写写冲突 "
                     "{writes} 个、峰值 {peak} 槽（按声明起点 "
                     "{declared_offset}：{declared_windows} / "
                     "{declared_writes} / {declared_peak}）。"
                     "每个候选都重新模拟过。"),
        "plc_keep": "声明的起点已经是最优之一。",
        "plc_col_offset": "起点",
        "plc_col_windows": "超容窗",
        "plc_col_writes": "写写冲突",
        "plc_col_peak": "峰值槽",
        "plc_candidates": "候选起点（其他 DAG 运行区间的边界）",
        "rpt_deadlines": "超期（deadline）",
        "rpt_deadline_row": "`{dag}` 于 {finish} 完成 — deadline {deadline}"
                            "（迟 {late}）",
        "rpt_suggestion_breaks": (" **注意**：该顺延会把 `{dag}` 推过 "
                                  "deadline（{finish} > {deadline}）— "
                                  "改错峰其他 DAG 或加容量。"),
    },
}


tp = make_lookup(DAGCONFLICT_I18N)
