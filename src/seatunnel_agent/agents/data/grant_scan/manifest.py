"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="grant_scan",
    workspace="data",
    route="/grants",
    page_title="Grant Surface",
    logo="GS",
    color="#9f1239",
    title_en="Grant Surface",
    title_zh="权限面扫描",
    desc_en="GRANT/REVOKE netting: public grants, broad privileges and PII-table exposure, graded",
    desc_zh="GRANT/REVOKE 净面 — 公开授权、宽权限与敏感表外授分级报出",
    api="seatunnel_agent.agents.data.grant_scan.api:router",
    group="governance",
    order=54,
    external=True,
    tools=(
        ToolManifest(
            name="grant_scan",
            ref="seatunnel_agent.agents.data.grant_scan.tools:grant_scan",
            desc_zh="权限面扫描（净授权面 + 公开/宽权限/敏感表外授）",
            desc_en="Grant-surface scan (net grants + public / broad / sensitive exposure)",
            router_en="Parse GRANT/REVOKE statements, net them, and grade "
                      "public grants, broad privileges and grants on "
                      "PII-flagged tables.",
            keywords=("授权", "权限", "grant", "revoke", "public",
                      "权限面", "外授"),
        ),
    ),
)
