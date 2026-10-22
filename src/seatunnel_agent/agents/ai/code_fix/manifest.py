"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest

MANIFEST = AgentManifest(
    name="code_fix",
    workspace="ai",
    route="/codefix",
    page_title="Code Fix Agent",
    logo="🩹",
    color="#e11d48",
    title_en="Code Fix Agent",
    title_zh="测试自愈 Agent",
    desc_en=("Run tests → read → patch → re-run until green, inside a git "
             "worktree; success verified by a final deterministic run"),
    desc_zh=("跑测试 → 读码 → 打补丁 → 复跑直到通过;在 git worktree 隔离"
             "执行,最终以确定性复跑验收"),
    # The run endpoint mutates the local filesystem, so it is OFF by
    # default: 403 unless CODEFIX_API_ALLOWED_DIRS whitelists the target.
    api="seatunnel_agent.agents.ai.code_fix.api:router",
    order=60,
    external=True,
)
