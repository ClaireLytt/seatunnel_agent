"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="join_audit",
    workspace="data",
    route="/joinaudit",
    page_title="Join Audit",
    logo="JA",
    color="#1e3a5f",
    title_en="Join Audit",
    title_zh="关联质量审计",
    desc_en="Two row sets and a key — match rates, orphan keys, null "
            "keys and the row explosion the join would produce, before "
            "the JOIN ships",
    desc_zh="两份数据行 + 关联键 — 匹配率/孤儿键/空键/行数爆炸系数,"
            "JOIN 上线前最后一道检查",
    api="seatunnel_agent.agents.data.join_audit.api:router",
    group="quality",
    order=96,
    external=True,
    tools=(
        ToolManifest(
            name="join_audit",
            ref="seatunnel_agent.agents.data.join_audit.tools:join_audit",
            desc_zh="关联质量审计（两份行 + 键 → 匹配率/爆炸系数）",
            desc_en="Join audit (two row sets + key → match/explosion)",
            router_en="Audit a JOIN before it ships: paste both sides "
                      "as CSV/JSONL plus the join key(s) ('k', "
                      "'lk=rk', comma-combined) and get each side's "
                      "match rate, orphan keys, null-key share, and "
                      "the row explosion factor with the worst "
                      "many-to-many keys. Distinct from "
                      "data_comparison (same-schema content diff) and "
                      "rt_offline_diff (realtime vs offline metrics). "
                      "No database connection.",
            keywords=("join", "关联", "匹配率", "孤儿", "爆炸", "多对多",
                      "审计", "键", "orphan", "explosion"),
        ),
    ),
)
