# -*- coding: utf-8 -*-
"""EN/ZH strings for PII scan reports and the /pii page.

Same pattern as ``sql_transpile.i18n``: one flat dict per language looked up
via ``tp(lang, key)``, Chinese as the fallback. Category labels live here so
the deterministic core stays language-free.
"""

from __future__ import annotations

PII_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "PII / Sensitive Column Scan",
        "rpt_root": "root",
        "rpt_dialect": "dialect",
        "rpt_stats": ("tables {tables} · columns {columns} · hits {total} "
                      "(high {high} / medium {medium} / low {low})"),
        "rpt_clean": "No sensitive columns matched the rule catalog.",
        "rpt_high": "High risk",
        "rpt_medium": "Medium risk",
        "rpt_low": "Low risk",
        "rpt_warnings": "Warnings",
        "rpt_matched_name": "column name matches",
        "rpt_matched_comment": "comment contains",
        "rpt_matched_both": "name + comment match",
        "rpt_weak": "weak match",
        "rpt_spread": "downstream spread {n} column(s), {unmasked} unmasked",
        "rpt_spread_masked": "downstream spread {n} column(s), all masked",
        "rpt_no_spread": "no downstream spread",
        "rpt_unmasked": "UNMASKED",
        "rpt_masked": "masked",
        "rpt_direct_copy": "direct copy",
        "rpt_escalated": "severity raised: unmasked spread",
        "rpt_disclaimer": (
            "> Deterministic scan over SQL files only — no database "
            "connection, nothing executed. Review hits before acting."),
        # category labels
        "cat_phone": "Phone number",
        "cat_id_card": "National ID",
        "cat_bank_card": "Bank card / account",
        "cat_passport": "Passport",
        "cat_email": "Email",
        "cat_person_name": "Person name",
        "cat_address": "Address",
        "cat_salary": "Salary / income",
        "cat_birthday": "Birth date",
        "cat_license_plate": "License plate",
        "cat_ip_address": "IP address",
    },
    "zh": {
        "rpt_title": "敏感数据扫描 (PII)",
        "rpt_root": "扫描目标",
        "rpt_dialect": "方言",
        "rpt_stats": ("表 {tables} · 列 {columns} · 命中 {total} "
                      "(高 {high} / 中 {medium} / 低 {low})"),
        "rpt_clean": "未命中任何敏感列规则。",
        "rpt_high": "高风险",
        "rpt_medium": "中风险",
        "rpt_low": "低风险",
        "rpt_warnings": "警告",
        "rpt_matched_name": "列名匹配",
        "rpt_matched_comment": "注释包含",
        "rpt_matched_both": "列名+注释匹配",
        "rpt_weak": "弱匹配",
        "rpt_spread": "下游扩散 {n} 列，其中 {unmasked} 处未脱敏",
        "rpt_spread_masked": "下游扩散 {n} 列，均已脱敏",
        "rpt_no_spread": "无下游扩散",
        "rpt_unmasked": "未脱敏",
        "rpt_masked": "已脱敏",
        "rpt_direct_copy": "直接复制",
        "rpt_escalated": "严重度已升级：存在未脱敏扩散",
        "rpt_disclaimer": (
            "> 仅基于 SQL 文件的确定性扫描 — 不连接数据库、不执行任何语句。"
            "处置前请人工复核。"),
        "cat_phone": "手机号",
        "cat_id_card": "身份证号",
        "cat_bank_card": "银行卡/账号",
        "cat_passport": "护照号",
        "cat_email": "邮箱",
        "cat_person_name": "姓名",
        "cat_address": "地址",
        "cat_salary": "工资/收入",
        "cat_birthday": "出生日期",
        "cat_license_plate": "车牌号",
        "cat_ip_address": "IP 地址",
    },
}


def normalize_lang(lang: str | None) -> str:
    return "en" if (lang or "").lower().startswith("en") else "zh"


def tp(lang: str, key: str) -> str:
    lang = normalize_lang(lang)
    return PII_I18N.get(lang, {}).get(key) or PII_I18N["zh"].get(key, key)


def category_label(lang: str, category: str) -> str:
    """Localized category name; custom categories fall back to the raw id."""
    key = f"cat_{category}"
    text = PII_I18N[normalize_lang(lang)].get(key) or PII_I18N["zh"].get(key)
    return text or category
