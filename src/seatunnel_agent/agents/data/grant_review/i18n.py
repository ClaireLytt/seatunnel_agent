"""EN/ZH strings for the grant-review reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

GR_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Permission Application Review",
        "rpt_scope": "**{n}** application(s) · reject {reject} / "
                     "downgrade {downgrade} / approve {approve}",
        "rpt_reviews": "Reviews (riskiest first)",
        "col_applicant": "applicant",
        "col_risk": "risk",
        "col_decision": "decision",
        "col_reasons": "risk factors",
        "col_downgrades": "suggested downgrades",
        "dec_approve": "approve",
        "dec_downgrade": "approve downgraded",
        "dec_reject": "reject",
        "dg_mask_s3": "mask or drop the S3 columns",
        "dg_narrow_columns": "name the columns instead of whole tables",
        "dg_read_only": "grant read-only",
        "dg_cap_90d": "cap the term at 90 days",
        "dg_ask_purpose": "ask for a concrete purpose",
        "rpt_disclaimer": "> Transparent scoring: S3 columns (direct "
                          "identifiers/money) 25 each (cap 2), S2 "
                          "quasi-identifiers 5 each (cap 3), whole-table "
                          "+20, write for a non-write role +30, term "
                          ">90d/permanent +8/15, thin purpose +15. "
                          "Reject at 70, downgrade at 40.",
        "rpt_llm_note": "Review note (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "权限申请审核",
        "rpt_scope": "**{n}** 份申请 · 拒绝 {reject} / 降级批准 "
                     "{downgrade} / 批准 {approve}",
        "rpt_reviews": "审核结果（风险高在前）",
        "col_applicant": "申请人",
        "col_risk": "风险分",
        "col_decision": "结论",
        "col_reasons": "风险点",
        "col_downgrades": "降级建议",
        "dec_approve": "批准",
        "dec_downgrade": "降级批准",
        "dec_reject": "拒绝",
        "dg_mask_s3": "S3 列脱敏或剔除",
        "dg_narrow_columns": "按列申请，不给整表",
        "dg_read_only": "只给只读",
        "dg_cap_90d": "期限压到 90 天",
        "dg_ask_purpose": "补充具体用途",
        "rpt_disclaimer": "> 透明打分：S3 列（直接标识/资金）每个 25 分"
                          "（最多计 2 个）、S2 准标识每个 5 分（最多 3 "
                          "个）、整表 +20、非写角色要写 +30、期限 >90 天/"
                          "永久 +8/15、用途过短 +15。70 分拒绝、40 分"
                          "降级。",
        "rpt_llm_note": "审核意见草稿（LLM — 发送前请复核）",
    },
}

tp = make_lookup(GR_I18N)
