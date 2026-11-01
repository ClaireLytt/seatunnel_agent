"""EN/ZH strings for the SeaTunnel-config-draft reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

SG_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "SeaTunnel Job Draft",
        "rpt_scope": "`{source}` → `{sink}` · table `{table}` "
                     "({columns} column(s)) · job.mode **{mode}** · "
                     "lint: {errors} error(s) / {warns} warning(s)",
        "rpt_params": "Parameters",
        "col_param": "parameter",
        "col_state": "state",
        "state_filled": "filled from the DDL",
        "state_placeholder": "example value — replace before running",
        "rpt_hocon": "job.conf (lints clean in Config Lint)",
        "rpt_warnings": "Notes",
        "rpt_disclaimer": "> Generated from the DDL and the connector "
                          "catalog — database/table/topic parameters "
                          "come from the table name, everything else "
                          "carries the documented example and is listed "
                          "above as a placeholder. Replace hosts and "
                          "credentials, then validate against the real "
                          "environment.",
        "rpt_llm_note": "Job review (LLM — review before running)",
    },
    "zh": {
        "rpt_title": "SeaTunnel 作业草稿",
        "rpt_scope": "`{source}` → `{sink}` · 表 `{table}`（{columns} 列）"
                     "· job.mode **{mode}** · lint: {errors} 错误 / "
                     "{warns} 警告",
        "rpt_params": "参数",
        "col_param": "参数",
        "col_state": "状态",
        "state_filled": "已按 DDL 填充",
        "state_placeholder": "示例值 — 运行前请替换",
        "rpt_hocon": "job.conf（配置体检零错误）",
        "rpt_warnings": "说明",
        "rpt_disclaimer": "> 由 DDL 与连接器目录生成 — 库/表/topic 参数"
                          "取自表名,其余参数带文档示例值并已在上表列为"
                          "待替换项。替换主机与凭据后,再对真实环境"
                          "验证。",
        "rpt_llm_note": "作业评审（LLM — 运行前请复核）",
    },
}

tp = make_lookup(SG_I18N)
