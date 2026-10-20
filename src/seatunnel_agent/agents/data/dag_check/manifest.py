"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest

MANIFEST = AgentManifest(
    name="dag_check",
    workspace="data",
    route="/dagcheck",
    page_title="DAG Check",
    logo="🗓️",
    color="#0f766e",
    title_en="DAG Check",
    title_zh="调度 DAG 体检",
    desc_en="Cycles, broken upstream, dead jobs — plus execution batches and the critical path",
    desc_zh="环/断链/死作业检测 — 并给出执行分批与关键路径",
    # api intentionally unset: the router is mounted unconditionally by the
    # launcher (the React page depends on it), not behind --api.
    render="",  # React static mount serves this route (frontend/dag_check)
    group="governance",
    order=60,
    external=True,
)
