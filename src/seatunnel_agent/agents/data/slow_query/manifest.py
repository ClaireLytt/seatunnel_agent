"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="slow_query",
    workspace="data",
    route="/slowquery",
    page_title="Slow Query",
    logo="SQ",
    color="#9f1239",
    title_en="Slow-Query RCA",
    title_zh="慢查询根因",
    desc_en="Run metrics x history baseline — skew, scan blow-up, spill, "
            "GC, queueing or small files, ranked with prescriptions",
    desc_zh="执行指标 × 历史基线 — 倾斜/扫描暴涨/溢写/GC/排队/小文件，按占比排序附处方",
    api="seatunnel_agent.agents.data.slow_query.api:router",
    group="quality",
    order=17,
    external=True,
    tools=(
        ToolManifest(
            name="slow_query",
            ref="seatunnel_agent.agents.data.slow_query.tools:slow_query",
            desc_zh="慢查询根因（指标 JSON + 历史基线 → 排序根因与处方）",
            desc_en="Slow-query RCA (metrics + baseline → ranked causes)",
            router_en="Diagnose why a query ran slow from its execution "
                      "metrics (per-stage task max/median, spill, GC, "
                      "queue time, scan bytes) and an optional history "
                      "baseline: skew, scan blow-up, shuffle spill, GC "
                      "pressure, queue wait or small files — ranked by "
                      "estimated share, each with a prescription.",
            keywords=("慢查询", "根因", "slow", "rca", "为什么慢",
                      "拖尾", "straggler", "gc", "溢写", "spill",
                      "排队", "小文件"),
        ),
    ),
)
