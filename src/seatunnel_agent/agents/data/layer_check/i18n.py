"""EN/ZH strings for the layer-check reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

LC_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Warehouse Layering Check",
        "rpt_scope": "**{tables}** table(s) · **{edges}** lineage "
                     "edge(s) · layers: {layers}",
        "rpt_findings": "Findings (worst first)",
        "col_code": "code",
        "col_sev": "severity",
        "col_detail": "evidence",
        "col_rx": "prescription",
        "sev_high": "high",
        "sev_mid": "mid",
        "sev_low": "low",
        "LC001": "layer skip — `{dst}` ({dst_layer}) reads `{src}` "
                 "({src_layer}), bypassing {skipped} layer(s)",
        "LC002": "reverse dependency — `{dst}` ({dst_layer}) reads "
                 "`{src}` ({src_layer}): the layering is inverted",
        "LC003": "same-layer chaining — `{dst}` reads `{src}` inside "
                 "{layer}",
        "LC004": "unknown layer — {count} table(s) map to no rank: "
                 "{tables}",
        "rx_LC001": "route the read through the modeling layer (build or "
                    "reuse the dwd/dws table in between)",
        "rx_LC002": "invert it: move the shared logic down, or the "
                    "higher table's logic up — never read upward",
        "rx_LC003": "aggregates stacked on aggregates drift apart; "
                    "derive both from the layer below",
        "rx_LC004": "rename to a layered prefix or add the prefix to the "
                    "custom layer map",
        "rpt_clean": "Every edge respects the layering.",
        "rpt_disclaimer": "> Deterministic walk of the SQL lineage; "
                          "layers come from name prefixes (built-in "
                          "ods/stg=0, dwd/dim=1, dws/dwm=2, ads/rpt/"
                          "app=3; tmp ignored) or a custom map. Lineage "
                          "is parsed from the submitted SQL only.",
        "rpt_llm_note": "Layering note (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "数仓分层体检",
        "rpt_scope": "**{tables}** 张表 · **{edges}** 条血缘边 · "
                     "分层：{layers}",
        "rpt_findings": "发现（严重在前）",
        "col_code": "编码",
        "col_sev": "级别",
        "col_detail": "证据",
        "col_rx": "处方",
        "sev_high": "高",
        "sev_mid": "中",
        "sev_low": "低",
        "LC001": "跨层引用 — `{dst}`（{dst_layer}）直读 `{src}`"
                 "（{src_layer}），跳过 {skipped} 层",
        "LC002": "反向依赖 — `{dst}`（{dst_layer}）读了 `{src}`"
                 "（{src_layer}）：分层被倒置",
        "LC003": "同层叠加 — {layer} 层内 `{dst}` 读 `{src}`",
        "LC004": "未知分层 — {count} 张表对不上任何前缀：{tables}",
        "rx_LC001": "经模型层中转（在中间补建或复用 dwd/dws 表）",
        "rx_LC002": "倒回来：公共逻辑下沉，或上层逻辑上移 — 永远不要"
                    "向上读",
        "rx_LC003": "聚合叠聚合会口径漂移；两张表都从下一层推导",
        "rx_LC004": "改成分层前缀命名，或把前缀加进自定义分层表",
        "rpt_clean": "所有血缘边都符合分层拓扑。",
        "rpt_disclaimer": "> 对 SQL 血缘的确定性检查；分层来自命名前缀"
                          "（内置 ods/stg=0、dwd/dim=1、dws/dwm=2、"
                          "ads/rpt/app=3，tmp 忽略）或自定义分层表。"
                          "血缘仅来自提交的 SQL。",
        "rpt_llm_note": "分层通报草稿（LLM — 发送前请复核）",
    },
}

tp = make_lookup(LC_I18N)
