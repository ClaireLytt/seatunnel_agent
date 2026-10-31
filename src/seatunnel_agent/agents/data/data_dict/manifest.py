"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="data_dict",
    workspace="data",
    route="/datadict",
    page_title="Data Dict",
    logo="DD",
    color="#4d7c0f",
    title_en="Data Dictionary",
    title_zh="数据字典生成",
    desc_en="DDL x SQL workload — per-column roles, usage counts and "
            "comment coverage; LLM drafts the missing descriptions",
    desc_zh="DDL × SQL 负载 — 逐列角色推断、使用频次与注释覆盖率,LLM 可代笔缺失描述",
    api="seatunnel_agent.agents.data.data_dict.api:router",
    group="governance",
    order=70,
    external=True,
    tools=(
        ToolManifest(
            name="data_dict",
            ref="seatunnel_agent.agents.data.data_dict.tools:data_dict",
            desc_zh="数据字典生成（目录 ± SQL → 角色/频次/覆盖率骨架）",
            desc_en="Data dictionary (catalog ± SQL → skeleton)",
            router_en="Generate a data-dictionary skeleton from an asset "
                      "catalog (JSON list or CREATE TABLE DDL), "
                      "optionally mined against a SQL workload: every "
                      "column gets an inferred role (key/time/measure/"
                      "flag/dimension from its name shape), its existing "
                      "comment, and filter/join/group-by usage counts; "
                      "per-table comment coverage names the gaps.",
            keywords=("字典", "数据字典", "dictionary", "注释", "字段描述",
                      "metadata", "comment", "覆盖率", "角色"),
        ),
    ),
)
