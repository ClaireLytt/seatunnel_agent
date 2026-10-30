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
    },
}


tp = make_lookup(DAGCONFLICT_I18N)
