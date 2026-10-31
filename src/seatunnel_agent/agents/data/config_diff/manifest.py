"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="config_diff",
    workspace="data",
    route="/configdiff",
    page_title="Config Diff",
    logo="CG",
    color="#9a3412",
    title_en="Config Diff",
    title_zh="配置漂移对比",
    desc_en="Two job configs semantically compared — graded changes "
            "with secrets masked, comments and ordering ignored",
    desc_zh="两份作业配置语义对比 — 差异按风险分级,密钥脱敏,注释与顺序不计",
    api="seatunnel_agent.agents.data.config_diff.api:router",
    group="build",
    order=85,
    external=True,
    tools=(
        ToolManifest(
            name="config_diff",
            ref="seatunnel_agent.agents.data.config_diff.tools:config_diff",
            desc_zh="配置漂移对比（双配置 → 分级语义差异）",
            desc_en="Config drift (two configs → graded differences)",
            router_en="Semantically compare two job configurations "
                      "(SeaTunnel HOCON, JSON or flat properties — "
                      "comments and ordering never count): every added, "
                      "removed or changed key comes back graded by what "
                      "it controls (high: parallelism/memory/checkpoint/"
                      "table/URL; mid: batch/retry/timeout knobs), with "
                      "secret-shaped values masked. The dev-vs-prod "
                      "release review in one paste. No environment "
                      "connection.",
            keywords=("配置", "diff", "漂移", "config", "对比", "环境",
                      "dev", "prod", "发布", "drift"),
        ),
    ),
)
