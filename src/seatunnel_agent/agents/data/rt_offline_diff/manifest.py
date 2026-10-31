"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="rt_offline_diff",
    workspace="data",
    route="/rtoffline",
    page_title="RT Offline Diff",
    logo="RO",
    color="#166534",
    title_en="RT-Offline Diff",
    title_zh="实时离线核对",
    desc_en="Two result sets keyed and compared under tolerance — "
            "missing keys, worst mismatches and systematic-bias verdicts",
    desc_zh="两份结果集按键对齐容差比较 — 缺失键、超差明细与系统性偏差判定",
    api="seatunnel_agent.agents.data.rt_offline_diff.api:router",
    group="quality",
    order=79,
    external=True,
    tools=(
        ToolManifest(
            name="rt_offline_diff",
            ref="seatunnel_agent.agents.data.rt_offline_diff.tools:rt_offline_diff",
            desc_zh="实时离线核对（双结果集 × 键 × 容差 → 差异 + 偏差判定）",
            desc_en="RT-offline reconciliation (two result sets → diffs)",
            router_en="Reconcile a realtime result set against the "
                      "offline one: paste both (CSV with a header, or "
                      "JSONL) plus the key column(s) and a relative "
                      "tolerance; rows are aligned by key and every "
                      "shared numeric column compared — missing keys on "
                      "either side, the worst over-tolerance mismatches, "
                      "and a systematic-bias verdict per metric "
                      "(realtime consistently lower → late data or "
                      "unclosed windows; higher → duplicate "
                      "consumption). No database connection.",
            keywords=("核对", "对账", "实时", "离线", "diff", "口径",
                      "reconcile", "一致性", "对不上", "差异"),
        ),
    ),
)
