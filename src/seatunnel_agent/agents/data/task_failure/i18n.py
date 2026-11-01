"""EN/ZH strings for the task-failure reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

TF_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Task Failure Attribution",
        "rpt_scope": "**{total}** failed task(s) · causes: {causes}",
        "rpt_clusters": "Root-cause clusters (biggest first)",
        "col_cause": "cause",
        "col_count": "tasks",
        "col_members": "members",
        "col_retry": "retry verdict",
        "col_sample": "sample error",
        "cause_dependency_missing": "dependency missing",
        "cause_resource": "resource",
        "cause_timeout": "timeout",
        "cause_connection": "connection",
        "cause_data_error": "data error",
        "cause_code_error": "code error",
        "cause_other": "other",
        "retry_transient": "transient — retry recovered it",
        "retry_futile": "futile — retries kept failing",
        "retry_mixed": "mixed",
        "retry_untried": "not retried",
        "rpt_rx": "Prescriptions",
        "rx_dependency_missing": "- dependency missing → check the "
            "upstream's schedule, then backfill "
            "(`seatunnel-agent backfill` / `rerun-plan`)",
        "rx_resource": "- resource → raise memory/slots or deconflict "
            "the window (`seatunnel-agent dagconflict`)",
        "rx_timeout": "- timeout → profile the run "
            "(`seatunnel-agent slowquery`)",
        "rx_connection": "- connection → check the endpoint and net "
            "path; retries usually recover these",
        "rx_data_error": "- data error → profile and repair the input "
            "(`seatunnel-agent sampleprofile` / `datarepair`)",
        "rx_code_error": "- code error → a code fix; retries are futile "
            "by construction",
        "rx_other": "- other → read the sample error; extend the "
            "classifier if a pattern recurs",
        "rpt_disclaimer": "> Deterministic regex classification over the "
                          "pasted export; clusters group identical "
                          "normalized error signatures, so one root "
                          "cause is one row however many tasks it "
                          "broke. No scheduler connection.",
        "rpt_llm_note": "Failure note (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "任务失败归因",
        "rpt_scope": "**{total}** 个失败任务 · 归因：{causes}",
        "rpt_clusters": "同根因聚类（任务多在前）",
        "col_cause": "归因",
        "col_count": "任务数",
        "col_members": "成员",
        "col_retry": "重试判定",
        "col_sample": "错误样例",
        "cause_dependency_missing": "依赖缺失",
        "cause_resource": "资源不足",
        "cause_timeout": "超时",
        "cause_connection": "连接",
        "cause_data_error": "数据异常",
        "cause_code_error": "代码错误",
        "cause_other": "其他",
        "retry_transient": "瞬态 — 重试已恢复",
        "retry_futile": "无效 — 重试仍失败",
        "retry_mixed": "部分恢复",
        "retry_untried": "未重试",
        "rpt_rx": "处方",
        "rx_dependency_missing": "- 依赖缺失 → 查上游排期，然后回刷"
            "（`seatunnel-agent backfill` / `rerun-plan`）",
        "rx_resource": "- 资源不足 → 调内存/slots 或错峰"
            "（`seatunnel-agent dagconflict`）",
        "rx_timeout": "- 超时 → 剖析运行（`seatunnel-agent slowquery`）",
        "rx_connection": "- 连接 → 查端点与网络路径；此类通常重试可恢复",
        "rx_data_error": "- 数据异常 → 剖析并修复输入"
            "（`seatunnel-agent sampleprofile` / `datarepair`）",
        "rx_code_error": "- 代码错误 → 改代码；重试注定无效",
        "rx_other": "- 其他 → 读错误样例；模式复现就扩充分类器",
        "rpt_disclaimer": "> 对粘贴导出的确定性正则归类；聚类按归一化"
                          "错误签名分组，同一根因无论打挂多少任务都只占"
                          "一行。不连调度器。",
        "rpt_llm_note": "失败通报草稿（LLM — 发送前请复核）",
    },
}

tp = make_lookup(TF_I18N)
