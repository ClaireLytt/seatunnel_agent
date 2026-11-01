"""EN/ZH strings for the partition-health reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

PH_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Partition Health",
        "rpt_scope": "**{tables}** table(s) · **{partitions}** "
                     "partition(s)",
        "rpt_findings": "Findings (worst first)",
        "col_code": "code",
        "col_sev": "severity",
        "col_table": "table",
        "col_detail": "evidence",
        "col_rx": "prescription",
        "sev_high": "high",
        "sev_mid": "mid",
        "sev_low": "low",
        "PH001": "date gaps — missing from {gaps} ({gap_count} gap(s))",
        "PH002": "empty partitions — {count}: {partitions}",
        "PH003": "size skew — {partition} is {size_gb:g} GB, {ratio}x "
                 "the median ({median_gb:g} GB)",
        "PH004": "latest partition surged — {partition} is {size_gb:g} "
                 "GB, {ratio}x the median ({median_gb:g} GB)",
        "PH005": "latest partition shrank — {partition} is {size_gb:g} "
                 "GB, {ratio}x the median ({median_gb:g} GB)",
        "rx_PH001": "backfill the hole (`seatunnel-agent backfill` / "
                    "`rerun-plan`), then find why the run skipped",
        "rx_PH002": "the writer ran but produced nothing — check its "
                    "filters and upstream volume that day",
        "rx_PH003": "a hot day or a double-load; verify duplicates "
                    "(`seatunnel-agent dupcheck`) before trusting it",
        "rx_PH004": "confirm the surge upstream before it cascades "
                    "(`seatunnel-agent datavolatility` on the source)",
        "rx_PH005": "yesterday lost volume — check late data or a "
                    "half-finished load before consumers read it",
        "rpt_clean": "Every partition looks healthy.",
        "rpt_disclaimer": "> Deterministic rules over the pasted "
                          "listing: gaps need date-shaped partition "
                          "values, skew 5/20x the table median, surge "
                          "3/10x, shrink under 0.3x. Freshness (did it "
                          "arrive on time) is the data_freshness "
                          "agent's job.",
        "rpt_llm_note": "Partition note (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "分区健康体检",
        "rpt_scope": "**{tables}** 张表 · **{partitions}** 个分区",
        "rpt_findings": "发现（严重在前）",
        "col_code": "编码",
        "col_sev": "级别",
        "col_table": "表",
        "col_detail": "证据",
        "col_rx": "处方",
        "sev_high": "高",
        "sev_mid": "中",
        "sev_low": "低",
        "PH001": "日期断档 — 缺失自 {gaps}（共 {gap_count} 处）",
        "PH002": "空分区 — {count} 个：{partitions}",
        "PH003": "大小倾斜 — {partition} 有 {size_gb:g} GB，是中位数"
                 "（{median_gb:g} GB）的 {ratio} 倍",
        "PH004": "最新分区暴涨 — {partition} 有 {size_gb:g} GB，是中位数"
                 "（{median_gb:g} GB）的 {ratio} 倍",
        "PH005": "最新分区缩水 — {partition} 只有 {size_gb:g} GB，是"
                 "中位数（{median_gb:g} GB）的 {ratio} 倍",
        "rx_PH001": "先回刷补洞（`seatunnel-agent backfill` / "
                    "`rerun-plan`），再查当天为什么没跑",
        "rx_PH002": "任务跑了但什么都没写 — 查当天过滤条件与上游量",
        "rx_PH003": "热点日或重复加载；先验重"
                    "（`seatunnel-agent dupcheck`）再采信",
        "rx_PH004": "先到上游确认暴涨再放行"
                    "（对源表跑 `seatunnel-agent datavolatility`）",
        "rx_PH005": "昨天掉量 — 在消费方读到之前查迟到数据或半截加载",
        "rpt_clean": "所有分区看起来健康。",
        "rpt_disclaimer": "> 对粘贴清单的确定性规则：断档需日期形分区值,"
                          "倾斜按表中位数 5/20 倍,暴涨 3/10 倍,缩水 "
                          "<0.3 倍。按不按时到是 data_freshness 的事。",
        "rpt_llm_note": "分区通报草稿（LLM — 发送前请复核）",
    },
}

tp = make_lookup(PH_I18N)
