"""EN/ZH strings for the data-volatility reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

VOL_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Data Volatility",
        "rpt_scope": "{metrics} metric(s): {detail}",
        "rpt_findings": "Volatility findings ({n})",
        "rpt_no_findings": "No volatility rule fired — the series look "
                           "steady.",
        "col_code": "code",
        "col_sev": "severity",
        "col_metric": "metric",
        "col_detail": "evidence",
        "sev_high": "high",
        "sev_mid": "mid",
        "sev_low": "low",
        "VA001": "surge on {date} — {value:g} vs rolling median "
                 "{window_median:g} ({change_pct:+g}%)",
        "VA002": "drop on {date} — {value:g} vs rolling median "
                 "{window_median:g} ({change_pct:+g}%)",
        "VA003": "level shift — recent median {to:g} vs prior "
                 "{from:g} ({shift_pct:+g}%)",
        "VA004": "flatline — stuck at {value:g} for the last {points} "
                 "points (since {since})",
        "VA005": "date gaps — missing from {gaps}",
        "VA006": "period-over-period change — {value:g} on {date} vs "
                 "previous point {prev:g} ({change_pct:+g}%)",
        "VA007": "vs {period} point(s) earlier — {value:g} on {date} vs "
                 "{base:g} ({change_pct:+g}%)",
        "rpt_prescription": "> Next step for a confirmed anomaly: trace "
                            "the polluting upstream with the "
                            "quality-trace agent "
                            "(`seatunnel-agent qualitytrace`).",
        "rpt_disclaimer": "> Deterministic rules over the submitted "
                          "series; spikes use a {window}-point rolling "
                          "median + MAD (K={k}), graded +50/100% for "
                          "surges and -30/60% for drops, level/DoD/PoP shifts "
                          "±30/60%. No database connection.",
        "rpt_llm_note": "Volatility note (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "数据波动分析",
        "rpt_scope": "{metrics} 个指标：{detail}",
        "rpt_findings": "波动发现（{n} 条）",
        "rpt_no_findings": "未命中任何波动规则 — 序列平稳。",
        "col_code": "编码",
        "col_sev": "级别",
        "col_metric": "指标",
        "col_detail": "证据",
        "sev_high": "高",
        "sev_mid": "中",
        "sev_low": "低",
        "VA001": "突增 {date} — {value:g}，滚动中位数 {window_median:g}"
                 "（{change_pct:+g}%）",
        "VA002": "突降 {date} — {value:g}，滚动中位数 {window_median:g}"
                 "（{change_pct:+g}%）",
        "VA003": "水平位移 — 近期中位数 {to:g}，此前 {from:g}"
                 "（{shift_pct:+g}%）",
        "VA004": "走平 — 最近 {points} 个点冻结在 {value:g}"
                 "（自 {since}）",
        "VA005": "日期断档 — 缺失自 {gaps}",
        "VA006": "环比突变 — {date} 为 {value:g}，上一点 {prev:g}"
                 "（{change_pct:+g}%）",
        "VA007": "同比突变 — {date} 为 {value:g}，{period} 点前为 "
                 "{base:g}（{change_pct:+g}%）",
        "rpt_prescription": "> 确认异常后的下一步：用质量根因追踪沿血缘"
                            "找污染上游（`seatunnel-agent qualitytrace`）。",
        "rpt_disclaimer": "> 对提交序列的确定性规则；突增/突降用 {window} "
                          "点滚动中位数 + MAD（K={k}），突增分级 "
                          "+50/100%、突降分级 -30/60%，水平位移与环比/同比 "
                          "±30/60%。不连数据库。",
        "rpt_llm_note": "波动通报草稿（LLM — 发送前请复核）",
    },
}

tp = make_lookup(VOL_I18N)
