"""Review harness: replay text2sql query logs through the static reviewer.

Reads ``logs/text2sql_queries.jsonl`` (written by the Text2SQL agent) and
runs the deterministic linter on every generated SQL, producing aggregate
quality stats.  This turns real generated queries into a regression suite
for both the Text2SQL generator and the review rules — no LLM, no database.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .agent import static_review_report
from .config import ReviewConfig
from .i18n import catalog_label
from .linter import normalize_dialect

DEFAULT_LOG = Path("logs") / "text2sql_queries.jsonl"


@dataclass
class HarnessEntry:
    index: int
    user_query: str
    sql: str
    exec_status: str          # text2sql execution status (success / error / ...)
    criticals: int = 0
    risks: int = 0
    suggestions: int = 0
    categories: list[str] = field(default_factory=list)
    # findings replayed from a cached LLM review of the identical SQL
    llm_matched: bool = False
    llm_criticals: int = 0
    llm_risks: int = 0
    llm_suggestions: int = 0

    @property
    def findings(self) -> int:
        return self.criticals + self.risks + self.suggestions

    def to_dict(self) -> dict:
        doc = {
            "index": self.index,
            "user_query": self.user_query,
            "sql": self.sql,
            "exec_status": self.exec_status,
            "criticals": self.criticals,
            "risks": self.risks,
            "suggestions": self.suggestions,
            "categories": self.categories,
        }
        if self.llm_matched:
            doc["llm"] = {
                "criticals": self.llm_criticals,
                "risks": self.llm_risks,
                "suggestions": self.llm_suggestions,
            }
        return doc


@dataclass
class HarnessResult:
    dialect: str = "hive"
    log_path: str = ""
    total_records: int = 0    # records in the log file
    reviewed: int = 0         # records with SQL that were linted
    skipped: int = 0          # records without generated SQL
    clean: int = 0            # reviewed queries with zero findings
    criticals: int = 0
    risks: int = 0
    suggestions: int = 0
    top_categories: list[tuple[str, int]] = field(default_factory=list)
    entries: list[HarnessEntry] = field(default_factory=list)
    # cached-LLM replay aggregates (populated when an llm_cache is passed)
    llm_matched: int = 0
    llm_criticals: int = 0
    llm_risks: int = 0
    llm_suggestions: int = 0

    @property
    def clean_rate(self) -> float:
        return self.clean / self.reviewed if self.reviewed else 0.0

    def to_dict(self) -> dict:
        doc = {
            "dialect": self.dialect,
            "log_path": self.log_path,
            "total_records": self.total_records,
            "reviewed": self.reviewed,
            "skipped": self.skipped,
            "clean": self.clean,
            "clean_rate": round(self.clean_rate, 4),
            "criticals": self.criticals,
            "risks": self.risks,
            "suggestions": self.suggestions,
            "top_categories": [
                {"category": c, "count": n} for c, n in self.top_categories
            ],
            "entries": [e.to_dict() for e in self.entries],
        }
        if self.llm_matched:
            doc["llm"] = {
                "matched": self.llm_matched,
                "criticals": self.llm_criticals,
                "risks": self.llm_risks,
                "suggestions": self.llm_suggestions,
            }
        return doc


def iter_log_records(log_path: str | Path):
    """Yield parsed JSONL records, silently skipping corrupt lines."""
    path = Path(log_path)
    if not path.is_file():
        raise FileNotFoundError(f"query log not found: {path}")
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict):
                yield rec


def load_llm_cache(log_path: str | Path | None = None) -> dict[str, dict]:
    """Latest LLM review per SQL hash from the review history log.

    Reads ``logs/sql_review.jsonl`` (written by ReviewLogger) and keeps, for
    every distinct SQL (``sql_sha256``), the most recent record produced by
    the LLM reviewer (``mode != "static"``).  Missing log → empty cache.
    """
    from .rlog import default_log_dir

    path = (Path(log_path) if log_path is not None
            else Path(default_log_dir()) / "sql_review.jsonl")
    cache: dict[str, dict] = {}
    if not path.is_file():
        return cache
    for rec in iter_log_records(path):
        sha = rec.get("sql_sha256")
        if not sha or rec.get("mode") == "static":
            continue
        sev = rec.get("severities") or {}
        cache[sha] = {  # later records overwrite: latest review wins
            "timestamp": rec.get("timestamp"),
            "criticals": int(sev.get("critical", 0)),
            "risks": int(sev.get("risk", 0)),
            "suggestions": int(sev.get("suggestion", 0)),
            "categories": rec.get("categories") or [],
        }
    return cache


def run_harness(
    log_path: str | Path = DEFAULT_LOG,
    dialect: str = "hive",
    limit: int | None = None,
    store=None,
    config: ReviewConfig | None = None,
    llm_cache: dict[str, dict] | None = None,
) -> HarnessResult:
    """Static-review every generated SQL in a text2sql query log."""
    from .rlog import sql_hash

    dialect = normalize_dialect(dialect)
    result = HarnessResult(dialect=dialect, log_path=str(log_path))
    cat_counter: Counter[str] = Counter()

    records = list(iter_log_records(log_path))
    if limit is not None and limit > 0:
        records = records[-limit:]

    for i, rec in enumerate(records):
        result.total_records += 1
        sql = (rec.get("generated_sql") or "").strip()
        if not sql:
            result.skipped += 1
            continue
        rep = static_review_report(sql, dialect, store=store, config=config)
        entry = HarnessEntry(
            index=i,
            user_query=str(rec.get("user_query") or ""),
            sql=sql,
            exec_status=str(rec.get("status") or ""),
            criticals=len(rep.criticals),
            risks=len(rep.risks),
            suggestions=len(rep.suggestions),
            categories=sorted({f.category for f in rep.findings}),
        )
        if llm_cache:
            cached = llm_cache.get(sql_hash(sql))
            if cached:
                entry.llm_matched = True
                entry.llm_criticals = cached["criticals"]
                entry.llm_risks = cached["risks"]
                entry.llm_suggestions = cached["suggestions"]
                result.llm_matched += 1
                result.llm_criticals += entry.llm_criticals
                result.llm_risks += entry.llm_risks
                result.llm_suggestions += entry.llm_suggestions
        result.reviewed += 1
        result.criticals += entry.criticals
        result.risks += entry.risks
        result.suggestions += entry.suggestions
        if not rep.findings:
            result.clean += 1
        cat_counter.update(entry.categories)
        result.entries.append(entry)

    result.top_categories = cat_counter.most_common(10)
    return result


def diff_against_baseline(baseline: dict, result: HarnessResult) -> dict:
    """Compare a harness run against a previous run's ``to_dict()`` JSON.

    Category counts are "queries affected" (one per query, not per finding),
    derived from each run's entries so old and new reports compare equally.
    """
    base_cats: Counter[str] = Counter()
    for e in baseline.get("entries", []):
        base_cats.update(e.get("categories") or [])
    cur_cats: Counter[str] = Counter()
    for e in result.entries:
        cur_cats.update(e.categories)

    changed = {
        cat: cur_cats.get(cat, 0) - base_cats.get(cat, 0)
        for cat in set(base_cats) | set(cur_cats)
        if cur_cats.get(cat, 0) != base_cats.get(cat, 0)
    }
    base_rate = float(baseline.get("clean_rate") or 0.0)
    return {
        "baseline_log": str(baseline.get("log_path") or ""),
        "reviewed": {"baseline": int(baseline.get("reviewed") or 0),
                     "current": result.reviewed},
        "clean_rate": {
            "baseline": round(base_rate, 4),
            "current": round(result.clean_rate, 4),
            "delta": round(result.clean_rate - base_rate, 4),
        },
        "severity_delta": {
            "critical": result.criticals - int(baseline.get("criticals") or 0),
            "risk": result.risks - int(baseline.get("risks") or 0),
            "suggestion": result.suggestions
            - int(baseline.get("suggestions") or 0),
        },
        "new_categories": sorted(set(cur_cats) - set(base_cats)),
        "resolved_categories": sorted(set(base_cats) - set(cur_cats)),
        "category_delta": dict(sorted(changed.items(),
                                      key=lambda kv: kv[1], reverse=True)),
    }


_HL = {
    "en": {
        "title": "# Text2SQL Review Harness",
        "log": "Query log",
        "dialect": "Dialect",
        "records": "Log records",
        "reviewed": "Queries reviewed",
        "skipped": "Skipped (no SQL)",
        "clean": "Clean queries",
        "severity_header": "## Findings by severity",
        "critical": "Critical",
        "risk": "Risk",
        "suggestion": "Suggestion",
        "cat_header": "## Top violated rules",
        "worst_header": "## Worst queries",
        "col_query": "User query",
        "col_sev": "critical / risk / suggestion",
        "col_cats": "Categories",
        "none": "No findings — all reviewed queries are clean.",
        "llm_header": "## Cached LLM reviews",
        "llm_matched": "Queries with a cached LLM review",
        "llm_findings": "LLM findings (critical / risk / suggestion)",
        "diff_header": "## Baseline comparison",
        "diff_baseline": "Baseline",
        "diff_reviewed": "Queries reviewed",
        "diff_clean_rate": "Clean rate",
        "diff_severity": "Findings delta (critical / risk / suggestion)",
        "diff_new": "New violated rules",
        "diff_resolved": "Resolved rules",
        "diff_changed": "Changed rules (queries affected)",
        "diff_none": "No change against the baseline.",
    },
    "zh": {
        "title": "# Text2SQL 审查 Harness",
        "log": "查询日志",
        "dialect": "SQL 方言",
        "records": "日志记录数",
        "reviewed": "已审查查询",
        "skipped": "跳过（无 SQL）",
        "clean": "无问题查询",
        "severity_header": "## 按严重级别统计",
        "critical": "严重",
        "risk": "风险",
        "suggestion": "建议",
        "cat_header": "## 高频违规规则",
        "worst_header": "## 问题最多的查询",
        "col_query": "用户问题",
        "col_sev": "严重 / 风险 / 建议",
        "col_cats": "违规类别",
        "none": "未发现问题 — 所有已审查查询均通过。",
        "llm_header": "## LLM 审查缓存复用",
        "llm_matched": "命中 LLM 审查缓存的查询",
        "llm_findings": "LLM 问题数（严重 / 风险 / 建议）",
        "diff_header": "## 与基线对比",
        "diff_baseline": "基线",
        "diff_reviewed": "已审查查询",
        "diff_clean_rate": "无问题率",
        "diff_severity": "问题数变化（严重 / 风险 / 建议）",
        "diff_new": "新增违规规则",
        "diff_resolved": "消失的违规规则",
        "diff_changed": "数量变化的规则（受影响查询数）",
        "diff_none": "与基线相比无变化。",
    },
}


def _render_diff_section(diff: dict, t: dict, lang: str) -> list[str]:
    def signed(n: int) -> str:
        return f"+{n}" if n > 0 else str(n)

    sev = diff.get("severity_delta") or {}
    rate = diff.get("clean_rate") or {}
    rev = diff.get("reviewed") or {}
    lines = [
        "",
        t["diff_header"],
        "",
        f"- {t['diff_baseline']}: `{diff.get('baseline_log', '')}`",
        f"- {t['diff_reviewed']}: {rev.get('baseline', 0)} → {rev.get('current', 0)}",
        f"- {t['diff_clean_rate']}: {rate.get('baseline', 0) * 100:.0f}% → "
        f"{rate.get('current', 0) * 100:.0f}% "
        f"({signed(round(rate.get('delta', 0) * 100))}%)",
        f"- {t['diff_severity']}: {signed(sev.get('critical', 0))} / "
        f"{signed(sev.get('risk', 0))} / {signed(sev.get('suggestion', 0))}",
    ]
    new = diff.get("new_categories") or []
    resolved = diff.get("resolved_categories") or []
    changed = diff.get("category_delta") or {}
    if new:
        lines.append(f"- {t['diff_new']}: "
                     + ", ".join(catalog_label(c, lang) for c in new))
    if resolved:
        lines.append(f"- {t['diff_resolved']}: "
                     + ", ".join(catalog_label(c, lang) for c in resolved))
    remaining = {c: d for c, d in changed.items()
                 if c not in set(new) | set(resolved)}
    if remaining:
        parts = [f"{catalog_label(c, lang)} ({signed(d)})"
                 for c, d in remaining.items()]
        lines.append(f"- {t['diff_changed']}: " + ", ".join(parts))
    if not (new or resolved or changed or any(sev.values())
            or rate.get("delta")):
        lines.append(f"- {t['diff_none']}")
    return lines


def render_harness_report(result: HarnessResult, lang: str = "en",
                          worst: int = 5,
                          baseline_diff: dict | None = None) -> str:
    """Render an aggregate markdown report for a harness run."""
    t = _HL.get(lang, _HL["en"])
    pct = f"{result.clean_rate * 100:.0f}%"
    lines = [
        t["title"],
        "",
        f"- {t['log']}: `{result.log_path}`",
        f"- {t['dialect']}: {result.dialect}",
        f"- {t['records']}: {result.total_records}",
        f"- {t['reviewed']}: {result.reviewed}",
        f"- {t['skipped']}: {result.skipped}",
        f"- {t['clean']}: {result.clean} ({pct})",
        "",
        t["severity_header"],
        "",
        f"- {t['critical']}: {result.criticals}",
        f"- {t['risk']}: {result.risks}",
        f"- {t['suggestion']}: {result.suggestions}",
    ]
    if result.llm_matched:
        lines += [
            "",
            t["llm_header"],
            "",
            f"- {t['llm_matched']}: {result.llm_matched}",
            f"- {t['llm_findings']}: {result.llm_criticals} / "
            f"{result.llm_risks} / {result.llm_suggestions}",
        ]
    if not (result.criticals or result.risks or result.suggestions):
        lines += ["", t["none"]]
        if baseline_diff:
            lines += _render_diff_section(baseline_diff, t, lang)
        return "\n".join(lines)

    if result.top_categories:
        lines += ["", t["cat_header"], ""]
        for cat, n in result.top_categories:
            lines.append(f"- {catalog_label(cat, lang)} ({n})")

    ranked = sorted(
        (e for e in result.entries if e.findings),
        key=lambda e: (e.criticals, e.risks, e.suggestions),
        reverse=True,
    )[:worst]
    if ranked:
        lines += ["", t["worst_header"], ""]
        lines.append(f"| # | {t['col_query']} | {t['col_sev']} | {t['col_cats']} |")
        lines.append("|---|------|------|------|")
        for e in ranked:
            q = e.user_query.replace("|", "\\|").replace("\n", " ")
            if len(q) > 60:
                q = q[:60] + "..."
            cats = ", ".join(catalog_label(c, lang) for c in e.categories[:4])
            lines.append(
                f"| {e.index} | {q} "
                f"| {e.criticals} / {e.risks} / {e.suggestions} | {cats} |"
            )
    if baseline_diff:
        lines += _render_diff_section(baseline_diff, t, lang)
    return "\n".join(lines)
