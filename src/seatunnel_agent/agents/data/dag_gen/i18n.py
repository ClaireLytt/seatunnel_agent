"""EN/ZH strings for the DAG-draft reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

DG_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Airflow DAG Draft",
        "rpt_title_dolphinscheduler": "DolphinScheduler Definition Draft",
        "rpt_title_azkaban": "Azkaban Flow Draft",
        "rpt_file_dolphinscheduler": "process definition JSON (parses "
                                     "clean — replace the <RUN> "
                                     "placeholders)",
        "rpt_file_azkaban": ".flow YAML (parses clean — replace the "
                            "<RUN> placeholders)",
        "rpt_scope": "dag `{dag_id}` · **{tasks}** task(s), **{edges}** "
                     "edge(s) · schedule `{schedule}` · "
                     "**{externals}** external upstream table(s)",
        "rpt_tasks": "Tasks",
        "col_task": "task_id",
        "col_table": "produces",
        "col_upstream": "upstream (in-DAG)",
        "col_external": "external upstream",
        "rpt_python": "dag.py (parses clean — replace the <RUN> "
                      "placeholders)",
        "rpt_warnings": "Parser warnings",
        "rpt_disclaimer": "> Drafted from the pasted SQL's lineage — one "
                          "task per write target, edges where a target "
                          "reads another. External upstream tables are "
                          "commented where sensors belong. dag_check "
                          "diagnoses the graph; this ships the file.",
        "rpt_llm_note": "Scheduling review (LLM — review before deploy)",
    },
    "zh": {
        "rpt_title": "Airflow DAG 草稿",
        "rpt_title_dolphinscheduler": "DolphinScheduler 工作流定义草稿",
        "rpt_title_azkaban": "Azkaban Flow 草稿",
        "rpt_file_dolphinscheduler": "工作流定义 JSON（可解析零错误 — "
                                     "替换 <RUN> 占位符后导入）",
        "rpt_file_azkaban": ".flow YAML（可解析零错误 — 替换 <RUN> "
                            "占位符后部署）",
        "rpt_scope": "dag `{dag_id}` · **{tasks}** 个任务、**{edges}** 条"
                     "依赖 · 调度 `{schedule}` · 脚本外上游表 "
                     "**{externals}** 张",
        "rpt_tasks": "任务",
        "col_task": "task_id",
        "col_table": "产出表",
        "col_upstream": "DAG 内上游",
        "col_external": "脚本外上游",
        "rpt_python": "dag.py（可解析零错误 — 替换 <RUN> 占位符后部署）",
        "rpt_warnings": "解析警告",
        "rpt_disclaimer": "> 由粘贴 SQL 的血缘生成 — 每个写入目标一个"
                          "任务,目标互读即依赖边;脚本外上游表在注释里"
                          "点名,该挂 sensor 的位置一目了然。dag_check "
                          "诊断图,本页出文件。",
        "rpt_llm_note": "调度评审（LLM — 部署前请复核）",
    },
}

tp = make_lookup(DG_I18N)
