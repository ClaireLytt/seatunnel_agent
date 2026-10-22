"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest

MANIFEST = AgentManifest(
    name="schema_drift",
    workspace="data",
    route="/schemadrift",
    page_title="Schema Drift",
    logo="🧬",
    color="#2563eb",
    title_en="Schema Drift",
    title_zh="Schema 漂移检查",
    desc_en="Diff two DDL snapshots — breaking / risk / info severity for every structural change",
    desc_zh="对比两份 DDL 快照 — 每处结构变更按破坏 / 风险 / 提示分级",
    api="seatunnel_agent.agents.data.schema_drift.api:router",
    group="governance",
    order=30,
    external=True,
)
