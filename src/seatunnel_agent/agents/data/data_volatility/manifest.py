"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="data_volatility",
    workspace="data",
    route="/datavolatility",
    page_title="Data Volatility",
    logo="VO",
    color="#15803d",
    title_en="Data Volatility",
    title_zh="数据波动分析",
    desc_en="Metric series — surges and drops vs a rolling median, level "
            "shifts, flatlines and date gaps, ranked with evidence",
    desc_zh="指标时间序列 — 滚动中位数判突增/突降、水平位移、走平、日期断档,按严重度排序附证据",
    api="seatunnel_agent.agents.data.data_volatility.api:router",
    group="quality",
    order=66,
    external=True,
    tools=(
        ToolManifest(
            name="data_volatility",
            ref="seatunnel_agent.agents.data.data_volatility.tools:data_volatility",
            desc_zh="数据波动分析（时间序列 → 突增/突降/位移/走平/断档）",
            desc_en="Data volatility (series → surges/drops/shifts/gaps)",
            router_en="Analyze metric time series (CSV with a "
                      "date,metric,value header, or JSONL with the same "
                      "fields; several metrics in one paste) and report "
                      "volatility ranked by severity: surges and drops "
                      "against a 7-point rolling median + MAD with dates "
                      "and magnitudes, level shifts of the recent median, "
                      "flatlines where a moving series froze, and date "
                      "gaps.",
            keywords=("波动", "突增", "突降", "volatility", "spike",
                      "drop", "环比", "同比", "走平", "断档", "趋势",
                      "指标异常"),
        ),
    ),
)
