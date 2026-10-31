"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="cost_allocation",
    workspace="data",
    route="/costalloc",
    page_title="Cost Allocation",
    logo="CA",
    color="#713f12",
    title_en="Cost Allocation",
    title_zh="成本分摊",
    desc_en="A usage inventory and unit prices — the per-owner bill with "
            "each team's cost drivers, unallocated spend called out "
            "first",
    desc_zh="用量清单 + 单价 — 逐归属方账单与各家成本大头,无主开销优先"
            "点名,谁用谁付一目了然",
    api="seatunnel_agent.agents.data.cost_allocation.api:router",
    group="governance",
    order=105,
    external=True,
    tools=(
        ToolManifest(
            name="cost_allocation",
            ref="seatunnel_agent.agents.data.cost_allocation.tools:"
                "cost_allocation",
            desc_zh="成本分摊（用量清单 → 逐归属方账单）",
            desc_en="Cost allocation (usage inventory → per-owner bill)",
            router_en="Split the platform bill by owner: paste a usage "
                      "inventory (owner, item, storage_gb, "
                      "compute_hours) with unit prices and get each "
                      "team's storage/compute/total with its top cost "
                      "drivers; spend without an owner is graded first "
                      "(nobody optimizes an unowned cost) and single-"
                      "owner concentration is flagged. storage_cost "
                      "prices what is held; this decides who pays. No "
                      "billing-system connection.",
            keywords=("成本", "分摊", "账单", "cost", "billing", "预算",
                      "归属", "owner", "chargeback", "计费"),
        ),
    ),
)
