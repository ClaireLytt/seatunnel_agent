"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="dq_rulegen",
    workspace="data",
    route="/dqrulegen",
    page_title="DQC Rule Draft",
    logo="RG",
    color="#065f46",
    title_en="DQC Rule Draft",
    title_zh="质量规则草稿",
    desc_en="A table sample in, a loadable DQC rules.yaml out — null "
            "head-room, enum domains, unique keys and a row-count "
            "guard, promised from what the data already keeps",
    desc_zh="表样例进,DQC 可直接加载的 rules.yaml 出 — 空值余量/枚举域/"
            "唯一键/行数护栏,只承诺数据已做到的",
    api="seatunnel_agent.agents.data.dq_rulegen.api:router",
    group="quality",
    order=98,
    external=True,
    tools=(
        ToolManifest(
            name="dq_rulegen",
            ref="seatunnel_agent.agents.data.dq_rulegen.tools:dq_rulegen",
            desc_zh="质量规则草稿（样例 → DQC rules.yaml）",
            desc_en="DQC rule draft (sample → loadable rules.yaml)",
            router_en="Draft the first DQC rule file nobody wants to "
                      "write by hand: paste a sample of the table plus "
                      "its name and get rules.yaml with a row_count "
                      "change guard, per-column null_rate caps "
                      "(observed rate plus head-room), unique checks "
                      "on key-shaped fully-distinct columns, and "
                      "enum_domain pins on low-cardinality columns. "
                      "The YAML round-trips through the DQC parser so "
                      "it loads as-is. sample_profile reports the "
                      "shape; data_quality runs the rules; this bridges "
                      "them. No database connection.",
            keywords=("dqc", "质量", "规则", "rules", "yaml", "生成",
                      "null", "enum", "unique", "草稿"),
        ),
    ),
)
