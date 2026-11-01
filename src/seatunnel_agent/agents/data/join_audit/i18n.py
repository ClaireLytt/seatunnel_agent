"""EN/ZH strings for the join-audit reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

JA_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Join Audit",
        "rpt_scope": "left **{lrows}** x right **{rrows}** on `{keys}` · "
                     "match **{lmatch:.0%}** / **{rmatch:.0%}** · joined "
                     "**{joined}** row(s), explosion **x{explosion:g}**",
        "rpt_clean": "The join is clean — full match, one-to-one, no "
                     "null keys.",
        "rpt_findings": "Findings",
        "col_sev": "sev",
        "col_code": "code",
        "col_side": "side",
        "col_issue": "issue",
        "JA001": "many-to-many keys multiply rows x{value:g} — worst: "
                 "{detail}",
        "JA002": "only {value:.0%} of left rows find a match — orphan "
                 "keys: {detail}",
        "JA003": "only {value:.0%} of right rows are reached — orphan "
                 "keys: {detail}",
        "JA004": "null/empty join keys ({detail}) never match anything",
        "side_left": "left",
        "side_right": "right",
        "side_both": "both",
        "rpt_disclaimer": "> Audited on the pasted rows only — rates on "
                          "a sample approximate the real join. A x1 "
                          "explosion with full match is a safe join; "
                          "anything else deserves a look before the "
                          "JOIN ships.",
        "rpt_llm_note": "Join review (LLM — review before acting)",
    },
    "zh": {
        "rpt_title": "关联质量审计",
        "rpt_scope": "左 **{lrows}** 行 x 右 **{rrows}** 行,键 `{keys}` · "
                     "匹配率 **{lmatch:.0%}** / **{rmatch:.0%}** · 关联后 "
                     "**{joined}** 行,爆炸系数 **x{explosion:g}**",
        "rpt_clean": "关联干净 — 全匹配、一对一、无空键。",
        "rpt_findings": "发现",
        "col_sev": "级",
        "col_code": "编码",
        "col_side": "侧",
        "col_issue": "问题",
        "JA001": "多对多键使行数放大 x{value:g} — 最严重: {detail}",
        "JA002": "左表仅 {value:.0%} 的行能匹配上 — 孤儿键: {detail}",
        "JA003": "右表仅 {value:.0%} 的行被关联到 — 孤儿键: {detail}",
        "JA004": "空关联键（{detail}）永远匹配不上",
        "side_left": "左",
        "side_right": "右",
        "side_both": "两侧",
        "rpt_disclaimer": "> 仅就粘贴的行审计 — 抽样上的比率近似真实"
                          "关联。爆炸系数 x1 且全匹配才是安全关联;其余"
                          "情况 JOIN 上线前都值得看一眼。",
        "rpt_llm_note": "关联评审（LLM — 采纳前请复核）",
    },
}

tp = make_lookup(JA_I18N)
