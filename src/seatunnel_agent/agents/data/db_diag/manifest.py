"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="db_diag",
    workspace="data",
    route="/dbdiag",
    page_title="DB Diag",
    logo="DB",
    color="#b33a2e",
    title_en="DB Diagnosis",
    title_zh="数据库运行诊断",
    desc_en="Status snapshot — pool pressure, thread storms, lock waits, "
            "deadlocks, slow hotspots and CPU, each with a prescription",
    desc_zh="状态快照 — 连接池/线程风暴/锁等待/死锁/慢查询热点/CPU,每条发现附处方",
    api="seatunnel_agent.agents.data.db_diag.api:router",
    group="governance",
    order=73,
    external=True,
    tools=(
        ToolManifest(
            name="db_diag",
            ref="seatunnel_agent.agents.data.db_diag.tools:db_diag",
            desc_zh="数据库运行诊断（快照 JSON → 发现 + 处方）",
            desc_en="DB runtime diagnosis (snapshot → findings)",
            router_en="Diagnose a database from a pasted status snapshot "
                      "(JSON with max_connections, threads_connected/"
                      "running, cpu_pct, lock waits, deadlocks, slow "
                      "queries — every section optional): rules flag "
                      "connection-pool pressure, running-thread storms, "
                      "long lock waits with the worst blocking pairs, "
                      "deadlocks, slow-query hotspots and CPU "
                      "saturation, each with evidence and a "
                      "prescription. No live connection.",
            keywords=("数据库", "诊断", "连接数", "锁", "死锁", "负载",
                      "db", "diagnosis", "processlist", "慢查询",
                      "lock", "deadlock"),
        ),
    ),
)
