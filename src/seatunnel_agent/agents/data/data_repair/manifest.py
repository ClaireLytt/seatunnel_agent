"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="data_repair",
    workspace="data",
    route="/datarepair",
    page_title="Data Repair",
    logo="RP",
    color="#9f1239",
    title_en="Data Repair",
    title_zh="一致性修复",
    desc_en="Duplicates, nulls and format drift turned into copy-ready "
            "repair SQL — dedup, backfill, standardize, cast",
    desc_zh="重复/空值/格式漂移自动生成修复 SQL 模板 — 去重、回填、标准化、数值转换",
    api="seatunnel_agent.agents.data.data_repair.api:router",
    group="quality",
    order=68,
    external=True,
    tools=(
        ToolManifest(
            name="data_repair",
            ref="seatunnel_agent.agents.data.data_repair.tools:data_repair",
            desc_zh="一致性修复方案（数据行 → 修复 SQL 模板清单）",
            desc_en="Repair plan (rows → ranked repair SQL templates)",
            router_en="Generate a consistency-repair plan from a pasted "
                      "data sample (CSV with a header row, or JSONL) and "
                      "a target table name: duplicate groups become "
                      "ROW_NUMBER dedup statements, high-null columns "
                      "get COALESCE backfill templates, whitespace/case "
                      "drift gets TRIM/LOWER standardization, numbers "
                      "stored as text get cleanup casts, and outlier "
                      "formats get rewrite templates — ranked by "
                      "severity, placeholders left for human decisions.",
            keywords=("修复", "清理", "repair", "去重", "空值", "回填",
                      "标准化", "fix", "cleanup", "一致性", "脏数据"),
        ),
    ),
)
