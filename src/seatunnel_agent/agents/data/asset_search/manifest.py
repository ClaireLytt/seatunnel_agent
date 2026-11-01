"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="asset_search",
    workspace="data",
    route="/assetsearch",
    page_title="Asset Search",
    logo="AS",
    color="#0d9488",
    title_en="Asset Search",
    title_zh="数据资产搜索",
    desc_en="Natural-language need x catalog (JSON or DDL) — explainable "
            "weighted hits with matched columns and locations",
    desc_zh="自然语言需求 × 资产目录(JSON/DDL) — 可解释的加权命中,附命中列与位置",
    api="seatunnel_agent.agents.data.asset_search.api:router",
    group="governance",
    order=69,
    external=True,
    tools=(
        ToolManifest(
            name="asset_search",
            ref="seatunnel_agent.agents.data.asset_search.tools:asset_search",
            desc_zh="数据资产搜索（目录 × 自然语言 → 可解释命中排行）",
            desc_en="Asset search (catalog x NL query → explainable hits)",
            router_en="Find the right table for a business need: paste "
                      "the asset catalog (a JSON list of tables with "
                      "comments and columns, or Hive-style CREATE TABLE "
                      "DDL) plus a natural-language query (Chinese or "
                      "English); tokens are expanded through a zh/en "
                      "synonym table and every asset is scored by "
                      "weighted matches — table name, table comment, "
                      "column name, column comment — returning an "
                      "explainable ranking with matched columns.",
            keywords=("找表", "资产", "搜索", "search", "catalog",
                      "找数", "哪张表", "字段", "数据集", "discovery"),
        ),
    ),
)
