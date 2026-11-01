"""EN/ZH strings for the cost-allocation reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

CA_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Cost Allocation",
        "rpt_scope": "**{owners}** owner(s) · total **{total:g}** · "
                     "storage @{sp:g}/GB, compute @{cp:g}/h · "
                     "unallocated **{unalloc:.1%}**",
        "rpt_owners": "Bill (biggest first)",
        "col_owner": "owner",
        "col_items": "items",
        "col_storage": "storage",
        "col_compute": "compute",
        "col_total": "total",
        "col_share": "share",
        "col_top": "top cost drivers",
        "rpt_findings": "Findings",
        "col_sev": "sev",
        "col_code": "code",
        "col_issue": "issue",
        "CA001": "{value:.1%} of the spend has no owner — nobody "
                 "optimizes an unowned cost",
        "CA002": "one owner carries {value:.1%} of the bill — check the "
                 "concentration before the next budget round",
        "rpt_clean": "Every cost has an owner and no one dominates.",
        "unallocated": "(unallocated)",
        "rpt_disclaimer": "> Priced from the pasted inventory and the "
                          "given unit prices only — same inventory, "
                          "same bill. Assign the unallocated items "
                          "first; they are where waste hides.",
        "rpt_llm_note": "Billing note (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "成本分摊",
        "rpt_scope": "**{owners}** 个归属方 · 总额 **{total:g}** · 存储 "
                     "@{sp:g}/GB、计算 @{cp:g}/时 · 无主占比 "
                     "**{unalloc:.1%}**",
        "rpt_owners": "账单（大头在前）",
        "col_owner": "归属",
        "col_items": "条目",
        "col_storage": "存储",
        "col_compute": "计算",
        "col_total": "合计",
        "col_share": "占比",
        "col_top": "成本大头",
        "rpt_findings": "发现",
        "col_sev": "级",
        "col_code": "编码",
        "col_issue": "问题",
        "CA001": "{value:.1%} 的开销没有归属 — 没人会优化无主成本",
        "CA002": "单一归属方占账单 {value:.1%} — 下轮预算前看一眼集中度",
        "rpt_clean": "每笔成本都有归属,且无一家独大。",
        "unallocated": "（无主）",
        "rpt_disclaimer": "> 仅按粘贴清单与给定单价计价 — 同清单必得同"
                          "账单。先把无主条目认领掉:浪费都藏在那里。",
        "rpt_llm_note": "账单通报（LLM — 发送前请复核）",
    },
}

tp = make_lookup(CA_I18N)
