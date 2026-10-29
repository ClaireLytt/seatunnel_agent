"""Chat/MCP tool entry points for the PII agent.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic:
no DB, no execution. ``lang`` is normalized here; the toolbox additionally
fills an empty ``lang`` with the server's default language.
"""

from __future__ import annotations


def _lang(lang: str) -> str:
    return "en" if (lang or "zh").strip().lower().startswith("en") else "zh"


def pii_scan(sql: str, dialect: str = "hive", lang: str = "") -> str:
    """敏感数据扫描（确定性，不连库不执行）：对 CREATE TABLE / INSERT
    语句做命名规则 × 字段血缘扫描，识别 PII 列（手机号/身份证/银行卡/
    邮箱/住址等），并沿血缘标出未脱敏的下游传播。返回 Markdown 报告。"""
    from seatunnel_agent.agents.data.pii_scan import (
        render_markdown,
        scan_sql_text,
    )

    if not (sql or "").strip():
        return "SQL 不能为空 / SQL must not be empty"
    try:
        report = scan_sql_text(sql, dialect=dialect)
    except Exception as exc:
        return f"扫描失败 / scan failed: {exc}"
    return render_markdown(report, lang=_lang(lang))


def pii_mask(sql: str, dialect: str = "hive",
             min_confidence: str = "low") -> str:
    """敏感列脱敏方案（确定性）：对扫描命中的列生成按类别脱敏的
    CREATE OR REPLACE VIEW DDL（手机留 3+4、身份证留 6+4、邮箱留首字母
    与域名、未知类别回退 md5），直接可执行。min_confidence=high 跳过
    弱命中（如裸 name 列）。"""
    from seatunnel_agent.agents.data.pii_scan import (
        plan_sql_text,
        render_mask_sql,
    )

    if not (sql or "").strip():
        return "SQL 不能为空 / SQL must not be empty"
    if min_confidence not in ("low", "high"):
        return f"min_confidence 必须是 low/high，收到: {min_confidence}"
    try:
        plan = plan_sql_text(sql, dialect=dialect,
                             min_confidence=min_confidence)
    except Exception as exc:
        return f"生成失败 / mask failed: {exc}"
    return render_mask_sql(plan)
