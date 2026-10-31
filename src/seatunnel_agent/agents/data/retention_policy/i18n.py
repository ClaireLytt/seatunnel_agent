"""EN/ZH strings for the retention-policy reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

RP_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Retention Advice",
        "rpt_scope": "as of **{today}** · **{tables}** table(s), "
                     "**{total:g}** GB held · **{reclaim:g}** GB "
                     "reclaimable · ● {high} / ◐ {medium} / ○ {low}",
        "rpt_tables": "Per-table advice (coldest first)",
        "col_table": "table",
        "col_parts": "partitions",
        "col_total": "GB held",
        "col_ttl": "suggested TTL",
        "col_cold": "GB cold",
        "col_archive": "archive",
        "col_purge": "purge",
        "days_suffix": "d",
        "rpt_findings": "Findings",
        "col_sev": "sev",
        "col_code": "code",
        "col_issue": "issue",
        "RP001": "{value:.0%} of the held size is past-TTL cold data",
        "RP002": "{value:g} partition(s) were never read — purge "
                 "candidates",
        "RP003": "{value:g} partition value(s) carry no parseable date "
                 "— advised blind",
        "rpt_clean": "Every partition is inside its keep window.",
        "rpt_disclaimer": "> TTL = the age of the oldest partition "
                          "anyone still reads, plus a 30-day grace, in "
                          "30-day steps; 'today' is the newest date in "
                          "the data, so the advice is reproducible. "
                          "Archive before purging; monthly jobs need a "
                          "wider access window than the default 90 "
                          "days.",
        "rpt_llm_note": "Retention review (LLM — review before acting)",
    },
    "zh": {
        "rpt_title": "生命周期建议",
        "rpt_scope": "基准日 **{today}** · **{tables}** 张表、持有 "
                     "**{total:g}** GB · 可释放 **{reclaim:g}** GB · "
                     "● {high} / ◐ {medium} / ○ {low}",
        "rpt_tables": "逐表建议（最冷在前）",
        "col_table": "表",
        "col_parts": "分区数",
        "col_total": "持有 GB",
        "col_ttl": "建议 TTL",
        "col_cold": "冷数据 GB",
        "col_archive": "可归档",
        "col_purge": "可清理",
        "days_suffix": "天",
        "rpt_findings": "发现",
        "col_sev": "级",
        "col_code": "编码",
        "col_issue": "问题",
        "RP001": "持有量的 {value:.0%} 是超 TTL 冷数据",
        "RP002": "{value:g} 个分区从未被读过 — 清理候选",
        "RP003": "{value:g} 个分区值解析不出日期 — 盲区",
        "rpt_clean": "所有分区都在保留窗口内。",
        "rpt_disclaimer": "> TTL = 仍有人读的最老分区年龄 + 30 天余量,按"
                          "30 天取整;基准日取数据内最新日期,同清单必得"
                          "同建议。先归档再清理;月度任务需要比默认 90 "
                          "天更宽的访问窗口。",
        "rpt_llm_note": "生命周期评审（LLM — 采纳前请复核）",
    },
}

tp = make_lookup(RP_I18N)
