"""EN/ZH strings for DAG optimization reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

DAGOPT_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "DAG Dependency Optimization",
        "rpt_stats": ("tasks {tasks} · edges {edges} · redundant edges "
                      "{redundant} · waves {waves} · max parallelism {width} "
                      "· ideal speedup {speedup}x"),
        "rpt_redundant": "Redundant serial dependencies (safe to remove)",
        "rpt_col_edge": "edge",
        "rpt_col_via": "already implied by",
        "rpt_no_redundant": "No redundant edges — the DAG is already a "
                            "transitive reduction.",
        "rpt_waves": "Parallel waves (tasks within a wave can run together)",
        "rpt_col_wave": "wave",
        "rpt_col_width": "width",
        "rpt_col_tasks": "tasks",
        "rpt_critical": "Critical path",
        "rpt_critical_note": ("duration {dur} of total {total} — this chain "
                              "bounds end-to-end latency"),
        "rpt_deadline_ok": ("**Deadline {deadline}: met** — the critical "
                            "path is {dur}."),
        "rpt_deadline_plan": ("**Deadline {deadline}: reachable** — halve "
                              "{plan} (in that order) and the critical "
                              "path fits."),
        "rpt_deadline_miss": ("**Deadline {deadline}: not reachable** — "
                              "critical path {dur}; even halving the top "
                              "bottlenecks is not enough. Restructure the "
                              "chain."),
        "rpt_bottlenecks": "Bottleneck sensitivity (halve one task — what "
                           "the critical path becomes)",
        "rpt_col_duration": "duration",
        "rpt_col_halved": "critical path if halved",
        "rpt_col_gain": "end-to-end gain",
        "rpt_makespan": "Makespan by worker count (what parallelism buys)",
        "rpt_col_workers": "workers",
        "rpt_col_makespan": "makespan",
        "rpt_col_speedup": "vs serial",
        "rpt_chains": "Serial chains (single-in/single-out — consider fusing)",
        "rpt_cycles": "On a cycle (unschedulable, excluded from analysis)",
        "rpt_action_plan": "Action plan (LLM — review before executing)",
        "rpt_optimized": "Optimized DAG (redundant edges removed — "
                         "paste back into your DAG tool)",
        "rpt_warnings": "Warnings",
        "rpt_disclaimer": ("> Deterministic analysis — redundant edges come "
                           "from transitive reduction, waves from Kahn "
                           "layering, the critical path from task durations "
                           "(default 1). No scheduler connection."),
    },
    "zh": {
        "rpt_title": "DAG 依赖优化",
        "rpt_stats": ("任务 {tasks} · 依赖边 {edges} · 冗余边 {redundant} · "
                      "并行批次 {waves} · 最大并行度 {width} · "
                      "理想加速比 {speedup}x"),
        "rpt_redundant": "冗余串行依赖（可安全删除）",
        "rpt_col_edge": "依赖边",
        "rpt_col_via": "已由此路径保证",
        "rpt_no_redundant": "没有冗余边 — DAG 已是传递归约。",
        "rpt_waves": "并行批次（同批次内的任务可同时运行）",
        "rpt_col_wave": "批次",
        "rpt_col_width": "宽度",
        "rpt_col_tasks": "任务",
        "rpt_critical": "关键路径",
        "rpt_critical_note": "时长 {dur} / 总时长 {total} — 该链决定端到端时延下限",
        "rpt_deadline_ok": "**SLA {deadline}：满足** — 关键路径 {dur}。",
        "rpt_deadline_plan": ("**SLA {deadline}：可达** — 依次把 {plan} "
                              "提速一半即可满足。"),
        "rpt_deadline_miss": ("**SLA {deadline}：不可达** — 关键路径 {dur}，"
                              "把最大的几个瓶颈都减半也不够，需要重构链路。"),
        "rpt_bottlenecks": "瓶颈敏感度（单个任务提速一半后关键路径变成多少）",
        "rpt_col_duration": "时长",
        "rpt_col_halved": "提速后关键路径",
        "rpt_col_gain": "端到端收益",
        "rpt_makespan": "按并发数估算的总工期（并行化值多少）",
        "rpt_col_workers": "并发数",
        "rpt_col_makespan": "总工期",
        "rpt_col_speedup": "相对串行",
        "rpt_chains": "串行链（单进单出 — 可考虑合并为一个任务）",
        "rpt_cycles": "处于环上（不可调度，已排除出分析）",
        "rpt_action_plan": "优化行动清单（LLM 生成 — 执行前请审阅）",
        "rpt_optimized": "优化后的 DAG（已删冗余边 — 可直接粘回 DAG 工具）",
        "rpt_warnings": "警告",
        "rpt_disclaimer": ("> 确定性分析 — 冗余边来自传递归约，批次来自 Kahn "
                           "分层，关键路径按任务时长（缺省 1）计算。不连调度器。"),
    },
}


tp = make_lookup(DAGOPT_I18N)
