"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="dag_gen",
    workspace="data",
    route="/daggen",
    page_title="DAG Draft",
    logo="DG",
    color="#14532d",
    title_en="DAG Draft",
    title_zh="调度文件生成",
    desc_en="Pipeline SQL in, an importable Airflow DAG out — one task "
            "per target, edges from the lineage, sensors flagged where "
            "external upstreams land",
    desc_zh="流水线 SQL 进,可直接 import 的 Airflow DAG 出 — 目标即任务/"
            "血缘即依赖/脚本外上游点名挂 sensor 的位置",
    api="seatunnel_agent.agents.data.dag_gen.api:router",
    group="build",
    order=101,
    external=True,
    tools=(
        ToolManifest(
            name="dag_gen",
            ref="seatunnel_agent.agents.data.dag_gen.tools:dag_gen",
            desc_zh="调度文件生成（流水线 SQL → Airflow dag.py）",
            desc_en="DAG draft (pipeline SQL → importable dag.py)",
            router_en="Draft the Airflow DAG nobody wants to hand-wire: "
                      "paste the pipeline SQL and every write target "
                      "becomes a BashOperator task with a <RUN table> "
                      "placeholder, dependency edges come from which "
                      "targets read which, and source tables produced "
                      "outside the script are commented where sensors "
                      "belong. The file passes ast.parse so it always "
                      "imports. dag_check diagnoses the graph; this "
                      "ships the scheduler file. No scheduler "
                      "connection.",
            keywords=("airflow", "dag", "调度", "依赖", "生成", "任务",
                      "sensor", "血缘", "schedule", "部署"),
        ),
    ),
)
