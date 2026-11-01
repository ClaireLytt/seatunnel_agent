"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="sql_diff",
    workspace="data",
    route="/sqldiff",
    page_title="SQL Diff",
    logo="SD",
    color="#9a3412",
    title_en="SQL Diff",
    title_zh="SQL 语义对比",
    desc_en="Two versions of pipeline SQL — the differences that change "
            "meaning, graded: dropped columns, flipped filters, "
            "aggregation shifts; formatting never counts",
    desc_zh="两版取数 SQL — 只报改变语义的差异并分级:删列/过滤翻转/"
            "聚合口径漂移,纯格式化从不计入",
    api="seatunnel_agent.agents.data.sql_diff.api:router",
    group="build",
    order=91,
    external=True,
    tools=(
        ToolManifest(
            name="sql_diff",
            ref="seatunnel_agent.agents.data.sql_diff.tools:sql_diff",
            desc_zh="SQL 语义对比（两版 SQL → 分级语义差异）",
            desc_en="SQL semantic diff (two versions → graded changes)",
            router_en="Compare two versions of pipeline/ETL SQL "
                      "semantically: statements pair by write target, "
                      "then dropped output columns and INSERT "
                      "INTO/OVERWRITE flips grade breaking; column "
                      "expression, WHERE and GROUP BY/HAVING changes "
                      "and source tables joining in or dropping out "
                      "grade risk; new statements or columns grade "
                      "info. Reformatting, aliases and ordering never "
                      "count. Use before merging a changed SQL job. No "
                      "database connection.",
            keywords=("diff", "对比", "sql", "语义", "版本", "评审",
                      "口径", "变更", "merge", "review"),
        ),
    ),
)
