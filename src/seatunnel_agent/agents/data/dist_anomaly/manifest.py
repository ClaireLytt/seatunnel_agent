"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="dist_anomaly",
    workspace="data",
    route="/distanomaly",
    page_title="Dist Anomaly",
    logo="DA",
    color="#9a3412",
    title_en="Distribution Drift",
    title_zh="数据分布异常",
    desc_en="Baseline vs current sample — mean shifts, null/unique jumps, "
            "category share drift, kind changes, ranked by severity",
    desc_zh="基线 vs 当前样本 — 均值漂移、空值/唯一率突变、类别占比漂移、类型变化，按严重度排序",
    api="seatunnel_agent.agents.data.dist_anomaly.api:router",
    group="quality",
    order=64,
    external=True,
    tools=(
        ToolManifest(
            name="dist_anomaly",
            ref="seatunnel_agent.agents.data.dist_anomaly.tools:dist_anomaly",
            desc_zh="数据分布异常检测（基线 vs 当前样本 → 漂移发现）",
            desc_en="Distribution drift (baseline vs current → findings)",
            router_en="Compare a baseline data sample against the current "
                      "one (CSV with a header row, JSONL, or a "
                      "sample_profile JSON) and report distribution "
                      "drift ranked by severity: schema adds/removes, "
                      "mean shifts, null and unique-rate jumps, category "
                      "share drift with the biggest movers, appeared or "
                      "vanished categories, dominant-kind changes.",
            keywords=("分布", "漂移", "drift", "异常", "均值", "占比",
                      "distribution", "anomaly", "基线", "baseline",
                      "突变"),
        ),
    ),
)
