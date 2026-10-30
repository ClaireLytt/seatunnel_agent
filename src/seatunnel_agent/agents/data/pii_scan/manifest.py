"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="pii_scan",
    workspace="data",
    route="/pii",
    page_title="PII Scan",
    logo="PS",
    color="#dc2626",
    title_en="PII Scan",
    title_zh="敏感数据扫描 PII",
    desc_en="Naming rules × column lineage — find sensitive columns and flag unmasked downstream spread",
    desc_zh="命名规则 × 字段血缘 — 识别敏感列并标出未脱敏的下游扩散",
    api="seatunnel_agent.agents.data.pii_scan.api:router",
    group="governance",
    order=50,
    external=True,
    tools=(
        ToolManifest(
            name="pii_scan",
            ref="seatunnel_agent.agents.data.pii_scan.tools:pii_scan",
            desc_zh="敏感列扫描（命名规则 × 血缘，标未脱敏传播）",
            desc_en="Sensitive-column scan (naming rules × lineage, flags unmasked spread)",
            router_en="Find sensitive columns via naming rules × column lineage and "
                      "flag unmasked downstream spread.",
            keywords=("敏感", "pii", "手机号", "身份证"),
        ),
        ToolManifest(
            name="pii_mask",
            ref="seatunnel_agent.agents.data.pii_scan.tools:pii_mask",
            desc_zh="命中列的脱敏视图 DDL（按类别表达式，可执行）",
            desc_en="Masked-view DDL for flagged columns (category-appropriate, executable)",
            router_en="Generate executable masked-view DDL for flagged sensitive "
                      "columns, with a coverage footer.",
            keywords=("脱敏", "mask", "打码", "脱敏视图", "masked view"),
        ),
    ),
)
