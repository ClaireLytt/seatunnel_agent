# -*- coding: utf-8 -*-
"""EN/ZH strings for schema drift reports and the /schemadrift page."""

from __future__ import annotations

SDF_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Schema Drift Check",
        "rpt_old": "old",
        "rpt_new": "new",
        "rpt_dialect": "dialect",
        "rpt_stats": ("tables {tables_old} → {tables_new} · findings {total} "
                      "(breaking {breaking} / risk {risk} / info {info})"),
        "rpt_clean": "No schema drift — the two snapshots are identical.",
        "rpt_breaking": "Breaking",
        "rpt_risk": "Risk",
        "rpt_info": "Info",
        "rpt_warnings": "Warnings",
        "rpt_disclaimer": (
            "> Deterministic DDL diff — no database connection, nothing "
            "executed. Pair with /impact for SQL logic changes."),
        # finding messages, keyed by kind
        "msg_table_removed": "table removed",
        "msg_table_added": "table added",
        "msg_column_removed": "column removed (was {old})",
        "msg_column_added": "column added ({new})",
        "msg_type_changed": "type changed {old} → {new}",
        "msg_comment_changed": "comment changed “{old}” → “{new}”",
        "msg_partition_changed": "partition layout changed [{old}] → [{new}]",
        "msg_column_renamed": "possible rename {old} → {new} "
                              "(same type and comment)",
    },
    "zh": {
        "rpt_title": "Schema 漂移检查",
        "rpt_old": "旧版本",
        "rpt_new": "新版本",
        "rpt_dialect": "方言",
        "rpt_stats": ("表 {tables_old} → {tables_new} · 变更 {total} "
                      "(破坏 {breaking} / 风险 {risk} / 提示 {info})"),
        "rpt_clean": "未发现 Schema 漂移 — 两个快照结构一致。",
        "rpt_breaking": "破坏性变更",
        "rpt_risk": "风险变更",
        "rpt_info": "提示",
        "rpt_warnings": "警告",
        "rpt_disclaimer": (
            "> 确定性 DDL 对比 — 不连接数据库、不执行任何语句。"
            "SQL 逻辑变更请配合变更影响分析 (/impact)。"),
        "msg_table_removed": "表被删除",
        "msg_table_added": "新增表",
        "msg_column_removed": "列被删除（原类型 {old}）",
        "msg_column_added": "新增列（{new}）",
        "msg_type_changed": "类型变更 {old} → {new}",
        "msg_comment_changed": "注释变更 “{old}” → “{new}”",
        "msg_partition_changed": "分区布局变更 [{old}] → [{new}]",
        "msg_column_renamed": "疑似改名 {old} → {new}（类型与注释一致）",
    },
}


def normalize_lang(lang: str | None) -> str:
    return "en" if (lang or "").lower().startswith("en") else "zh"


def tp(lang: str, key: str) -> str:
    lang = normalize_lang(lang)
    return SDF_I18N.get(lang, {}).get(key) or SDF_I18N["zh"].get(key, key)


def finding_message(lang: str, kind: str, old: str, new: str) -> str:
    tmpl = tp(lang, f"msg_{kind}")
    try:
        return tmpl.format(old=old, new=new)
    except (KeyError, IndexError):
        return tmpl
