"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="mock_data",
    workspace="data",
    route="/mockdata",
    page_title="Mock Data",
    logo="MK",
    color="#115e59",
    title_en="Mock Data",
    title_zh="测试数据生成",
    desc_en="A real sample in, shape-preserving mock rows out — ranges, "
            "formats and null rates carry over; sensitive columns are "
            "synthesized, never sampled",
    desc_zh="真实样例进,保形 mock 数据出 — 区间/格式/空值率保留,敏感列"
            "现场合成绝不取样,同种子必得同结果",
    api="seatunnel_agent.agents.data.mock_data.api:router",
    group="quality",
    order=95,
    external=True,
    tools=(
        ToolManifest(
            name="mock_data",
            ref="seatunnel_agent.agents.data.mock_data.tools:mock_data",
            desc_zh="测试数据生成（样例 → 保形 mock 行）",
            desc_en="Mock data (sample → shape-preserving rows)",
            router_en="Generate test rows that look like production "
                      "without being production: paste a CSV/JSONL "
                      "sample and get N deterministic rows — integers "
                      "and decimals stay in the observed range, dates "
                      "in the observed window, low-cardinality columns "
                      "follow the observed distribution, null rates "
                      "carry over, and sensitive columns (phone, ID "
                      "card, email, names) are synthesized fakes that "
                      "never copy a real value. Same sample + seed = "
                      "same rows. No database connection.",
            keywords=("mock", "测试数据", "造数", "样例", "合成", "假数据",
                      "seed", "fixture", "test", "data"),
        ),
    ),
)
