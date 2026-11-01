"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="grant_review",
    workspace="data",
    route="/grantreview",
    page_title="Grant Review",
    logo="GR",
    color="#8a4a2b",
    title_en="Grant Review",
    title_zh="权限申请审核",
    desc_en="Applications x sensitivity vocabulary — transparent risk "
            "scores with approve / downgrade / reject and concrete cuts",
    desc_zh="申请单 × 敏感级词表 — 透明风险分,批准/降级批准/拒绝并给具体降级建议",
    api="seatunnel_agent.agents.data.grant_review.api:router",
    group="governance",
    order=74,
    external=True,
    tools=(
        ToolManifest(
            name="grant_review",
            ref="seatunnel_agent.agents.data.grant_review.tools:grant_review",
            desc_zh="权限申请审核（申请单 JSON → 风险分 + 结论）",
            desc_en="Grant review (applications → risk + decisions)",
            router_en="Review data-permission applications (JSON object "
                      "or list: applicant, role, purpose, tables with "
                      "columns, duration, write flag): columns are "
                      "graded against a built-in sensitivity vocabulary "
                      "(S3 direct identifiers and money, S2 "
                      "quasi-identifiers), risk accrues from wildcards, "
                      "write-for-read roles, long terms and thin "
                      "purposes, and each application gets approve / "
                      "downgrade (with concrete cuts) / reject.",
            keywords=("权限", "审批", "申请", "grant", "permission",
                      "敏感", "审核", "风险", "approval", "脱敏"),
        ),
    ),
)
