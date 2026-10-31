"""EN/ZH strings for the distribution-anomaly reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

DIST_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Distribution Drift",
        "rpt_scope": "baseline **{base}** rows vs current **{cur}** rows · "
                     "{cols} common columns compared",
        "rpt_findings": "Drift findings ({n})",
        "rpt_no_findings": "No drift rule fired — the two samples look "
                           "alike.",
        "col_code": "code",
        "col_sev": "severity",
        "col_col": "column",
        "col_detail": "evidence",
        "sev_high": "high",
        "sev_mid": "mid",
        "sev_low": "low",
        "DA001": "schema change — column {change}",
        "DA002": "mean shift — {from:g} → {to:g} ({shift_pct}%)",
        "DA003": "null-rate jump — {from:g}% → {to:g}% (+{delta_pp}pp)",
        "DA004": "category share drift — L1 {l1}; biggest movers: {moved}",
        "DA005": "category set changed — appeared {appeared}; "
                 "vanished {vanished}",
        "DA006": "unique-rate jump — {from:g}% → {to:g}% ({delta_pp}pp)",
        "DA007": "dominant kind changed — {from} → {to}",
        "change_added": "added",
        "change_removed": "removed",
        "rpt_disclaimer": "> Rule-based comparison of two deterministic "
                          "sample profiles; thresholds: mean ±20/50%, "
                          "rates ±10/25pp, category L1 0.2/0.4. "
                          "No database connection.",
        "rpt_llm_note": "Drift note (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "数据分布漂移",
        "rpt_scope": "基线 **{base}** 行 vs 当前 **{cur}** 行 · "
                     "对比 {cols} 个共同列",
        "rpt_findings": "漂移发现（{n} 条）",
        "rpt_no_findings": "未命中任何漂移规则 — 两份样本分布一致。",
        "col_code": "编码",
        "col_sev": "级别",
        "col_col": "列",
        "col_detail": "证据",
        "sev_high": "高",
        "sev_mid": "中",
        "sev_low": "低",
        "DA001": "schema 变化 — 列被{change}",
        "DA002": "均值漂移 — {from:g} → {to:g}（{shift_pct}%）",
        "DA003": "空值率突变 — {from:g}% → {to:g}%（+{delta_pp}pp）",
        "DA004": "类别占比漂移 — L1 距离 {l1}；移动最大：{moved}",
        "DA005": "类别集合变化 — 新增 {appeared}；消失 {vanished}",
        "DA006": "唯一率突变 — {from:g}% → {to:g}%（{delta_pp}pp）",
        "DA007": "主类型变化 — {from} → {to}",
        "change_added": "新增",
        "change_removed": "移除",
        "rpt_disclaimer": "> 两份确定性抽样剖面的规则对比；阈值：均值 "
                          "±20/50%、比率 ±10/25pp、类别 L1 0.2/0.4。"
                          "不连数据库。",
        "rpt_llm_note": "漂移通报草稿（LLM — 发送前请复核）",
    },
}

tp = make_lookup(DIST_I18N)
