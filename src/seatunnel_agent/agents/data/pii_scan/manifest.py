"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest

MANIFEST = AgentManifest(
    name="pii_scan",
    workspace="data",
    route="/pii",
    page_title="PII Scan",
    logo="🔒",
    color="#dc2626",
    title_en="PII Scan",
    title_zh="敏感数据扫描 PII",
    desc_en="Naming rules × column lineage — find sensitive columns and flag unmasked downstream spread",
    desc_zh="命名规则 × 字段血缘 — 识别敏感列并标出未脱敏的下游扩散",
    # api intentionally unset: the router is mounted unconditionally by the
    # launcher (the React page depends on it), not behind --api.
    render="",  # React static mount serves this route (frontend/pii_scan)
    group="governance",
    order=50,
    external=True,
)
