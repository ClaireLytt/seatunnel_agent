"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="task_failure",
    workspace="data",
    route="/taskfailure",
    page_title="Task Failure",
    logo="TF",
    color="#b33a2e",
    title_en="Task Failure",
    title_zh="任务失败归因",
    desc_en="Failed-task export — causes classified, identical root "
            "causes clustered, retry effectiveness judged",
    desc_zh="失败任务导出 — 错误归类、同根因聚类、重试有效性判定,每类附处方",
    api="seatunnel_agent.agents.data.task_failure.api:router",
    group="build",
    order=80,
    external=True,
    tools=(
        ToolManifest(
            name="task_failure",
            ref="seatunnel_agent.agents.data.task_failure.tools:task_failure",
            desc_zh="任务失败归因（失败导出 → 根因聚类 + 重试判定）",
            desc_en="Task failure attribution (export → clusters)",
            router_en="Attribute scheduler task failures from a pasted "
                      "export (CSV or JSON list with task, error text, "
                      "retries, final status): errors are classified "
                      "(dependency missing / resource / timeout / "
                      "connection / data error / code error), identical "
                      "normalized error signatures cluster into one "
                      "root-cause group, retry effectiveness is judged "
                      "(transient / futile / mixed), and every class "
                      "carries a prescription. No scheduler connection.",
            keywords=("失败", "归因", "重试", "failure", "任务挂了",
                      "调度", "报错", "root cause", "聚类", "airflow"),
        ),
    ),
)
