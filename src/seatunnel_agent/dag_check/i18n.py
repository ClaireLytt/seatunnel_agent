# -*- coding: utf-8 -*-
"""EN/ZH strings for DAG check reports and the /dagcheck page."""

from __future__ import annotations

DAG_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Scheduling DAG Health Check",
        "rpt_root": "root",
        "rpt_stats": ("tables {tables} · edges {edges} · findings {total} "
                      "(error {error} / warn {warn} / info {info})"),
        "rpt_clean": "No scheduling hazards found.",
        "rpt_findings": "Findings",
        "rpt_batches": "Execution batches (tables in one wave can run in parallel)",
        "rpt_batch": "wave",
        "rpt_unschedulable": "Unschedulable (on cycles)",
        "rpt_critical": "Critical path (longest dependency chain)",
        "rpt_warnings": "Warnings",
        "rpt_disclaimer": (
            "> Deterministic graph analysis over SQL/SeaTunnel lineage — "
            "no scheduler connection, nothing executed."),
        "msg_cycle": "dependency cycle — unschedulable",
        "msg_dangling_mid": "mid-layer tables no job produces (broken upstream?)",
        "msg_unconsumed_mid": "mid-layer tables nothing consumes (dead jobs?)",
        "msg_isolated": "tables with no lineage edges at all",
    },
    "zh": {
        "rpt_title": "调度 DAG 体检",
        "rpt_root": "扫描目标",
        "rpt_stats": ("表 {tables} · 依赖边 {edges} · 发现 {total} "
                      "(错误 {error} / 警告 {warn} / 提示 {info})"),
        "rpt_clean": "未发现调度隐患。",
        "rpt_findings": "发现",
        "rpt_batches": "执行分批（同一批内的表可并行跑）",
        "rpt_batch": "批",
        "rpt_unschedulable": "无法调度（处于环上）",
        "rpt_critical": "关键路径（最长依赖链）",
        "rpt_warnings": "警告",
        "rpt_disclaimer": (
            "> 基于 SQL/SeaTunnel 血缘的确定性图分析 — 不连接调度系统、"
            "不执行任何作业。"),
        "msg_cycle": "依赖成环 — 无法调度",
        "msg_dangling_mid": "中间层表没有任何作业产出（上游断链？）",
        "msg_unconsumed_mid": "中间层表没有任何下游消费（死作业？）",
        "msg_isolated": "完全没有血缘边的表",
    },
}


def normalize_lang(lang: str | None) -> str:
    return "en" if (lang or "").lower().startswith("en") else "zh"


def tp(lang: str, key: str) -> str:
    lang = normalize_lang(lang)
    return DAG_I18N.get(lang, {}).get(key) or DAG_I18N["zh"].get(key, key)
