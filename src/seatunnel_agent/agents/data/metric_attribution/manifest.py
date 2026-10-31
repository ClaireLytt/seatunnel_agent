"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="metric_attribution",
    workspace="data",
    route="/metricattribution",
    page_title="Metric Attribution",
    logo="MA",
    color="#2f6f4f",
    title_en="Metric Attribution",
    title_zh="指标异动归因",
    desc_en="Two sliced result sets — the metric change decomposed "
            "exactly per dimension value, with concentration and "
            "mix-shift verdicts",
    desc_zh="两份按维度切分的结果 — 指标变动逐值精确分解,判单点事故与结构漂移",
    api="seatunnel_agent.agents.data.metric_attribution.api:router",
    group="quality",
    order=87,
    external=True,
    tools=(
        ToolManifest(
            name="metric_attribution",
            ref="seatunnel_agent.agents.data.metric_attribution.tools:metric_attribution",
            desc_zh="指标异动归因（双结果集 × 维度 → 逐值贡献分解）",
            desc_en="Metric attribution (two slices → contributions)",
            router_en="Answer 'the metric moved — which dimension value "
                      "did it': paste the baseline and current result "
                      "sets sliced by dimensions (CSV or JSONL) plus the "
                      "dimension and metric columns; the change "
                      "decomposes exactly and additively into per-value "
                      "contributions with shares (appeared and vanished "
                      "values included), plus verdicts for the top "
                      "contributor, single-value concentration and "
                      "offsetting mix shifts. No database connection.",
            keywords=("归因", "异动", "贡献", "attribution", "维度",
                      "为什么跌", "为什么涨", "分解", "渠道", "大盘"),
        ),
    ),
)
