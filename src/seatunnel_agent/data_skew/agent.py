"""Data Skew agent: static skew rules + LLM rewrite -> optimized SQL + report.

Pure static analysis — the SQL is never executed and no data source
connection is required. The LLM pass follows the fixed 5-step workflow
(analyze -> identify -> optimized SQL -> consistency check -> optimization
table) and the optimized SQL is written to ``<name>_optimized.sql``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..config import Settings
from ..llm import LLMClient
from .detector import detect_skew, normalize_dialect, split_statements
from .i18n import dsk, normalize_lang
from .prompts import build_system_prompt, build_user_prompt
from .report import Severity, SkewFinding, SkewReport, render_report

EventCallback = Callable[[str, dict[str, Any]], None]

DEFAULT_OUTPUT_NAME = "my_task_optimized.sql"


# ---------------------------------------------------------------------------
# Static-only entry points (no LLM)
# ---------------------------------------------------------------------------

def static_skew_report(sql: str, dialect: str = "spark", lang: str = "zh") -> SkewReport:
    """Static rules only: detect skew patterns, return the report object."""
    dialect = normalize_dialect(dialect)
    lang = normalize_lang(lang)
    findings, hints = detect_skew(sql, dialect, lang)
    return SkewReport(
        findings=findings,
        dialect=dialect,
        statement_count=len(split_statements(sql)),
        engine_hints=hints,
    )


def static_skew_check(sql: str, dialect: str = "spark", lang: str = "zh") -> str:
    """Static rules only: detect skew patterns, render the markdown report."""
    return render_report(static_skew_report(sql, dialect, lang), lang)


# ---------------------------------------------------------------------------
# LLM response parsing
# ---------------------------------------------------------------------------

_SQL_BLOCK_RE = re.compile(r"```sql\s*\n(.*?)```", re.IGNORECASE | re.DOTALL)

_SECTION_HEADS = {
    "optimized": ("## 优化后 SQL", "## Optimized SQL"),
    "consistency": ("## 一致性检查", "## Consistency Check"),
    "points": ("## 优化点说明", "## Optimization Points"),
}


def _find_heading(text: str, head: str) -> int:
    """Position of ``head`` at the start of a line (avoids matching the
    heading text quoted mid-sentence), or -1."""
    m = re.search(rf"(?m)^[ \t]{{0,3}}#{{2,3}}\s*{re.escape(head.lstrip('# '))}", text)
    return m.start() if m else -1


def _split_sections(text: str) -> dict[str, str]:
    """Split the LLM reply on the three fixed '## ' headings."""
    positions: list[tuple[int, str]] = []
    for name, heads in _SECTION_HEADS.items():
        for head in heads:
            idx = _find_heading(text, head)
            if idx != -1:
                positions.append((idx, name))
                break
    positions.sort()
    sections: dict[str, str] = {}
    for i, (idx, name) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        body = text[idx:end]
        body = body.split("\n", 1)[1] if "\n" in body else ""
        sections[name] = body.strip()
    return sections


def extract_optimized_sql(text: str) -> str:
    """The optimized SQL: first ```sql block inside the optimized section,
    falling back to the first ```sql block anywhere."""
    sections = _split_sections(text)
    scope = sections.get("optimized", "")
    m = _SQL_BLOCK_RE.search(scope) or _SQL_BLOCK_RE.search(text)
    return m.group(1).strip() if m else ""


_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")


def parse_optimization_table(text: str) -> list[SkewFinding]:
    """Parse the fixed optimization-point table into LLM findings."""
    sections = _split_sections(text)
    scope = sections.get("points") or text
    findings: list[SkewFinding] = []
    for line in scope.splitlines():
        m = _ROW_RE.match(line)
        if not m:
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        if len(cells) < 5:
            continue
        first = cells[0].lstrip("#").strip()
        if not first.isdigit():
            continue  # header / separator rows
        point, before, after, benefit = cells[1], cells[2], cells[3], cells[4]
        findings.append(
            SkewFinding(
                severity=Severity.MEDIUM,
                category="llm",
                location="-",
                description=point,
                before=before.strip("`"),
                after=after.strip("`"),
                benefit=benefit,
                suggestion=point,
                source="llm",
            )
        )
    return findings


def _consistency_notes(text: str) -> str:
    return _split_sections(text).get("consistency", "")


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

@dataclass
class SkewAnalysisResult:
    report: SkewReport
    markdown: str = ""      # rendered report
    llm_raw: str = ""       # full LLM reply (empty on static runs)
    used_llm: bool = False

    @property
    def optimized_sql(self) -> str:
        return self.report.optimized_sql

    @property
    def output_file(self) -> str:
        return self.report.output_file


class DataSkewAgent:
    """Static detector + optional LLM optimizer.

    ``analyze()`` always runs the static rules; with ``use_llm=True`` it also
    asks the LLM to rewrite the SQL following the 5-step workflow and writes
    the optimized SQL next to ``output_path``.
    """

    def __init__(
        self,
        settings: Settings,
        dialect: str = "spark",
        lang: str = "zh",
        on_event: EventCallback | None = None,
    ) -> None:
        self.settings = settings
        self.dialect = normalize_dialect(dialect)
        self.lang = normalize_lang(lang)
        self.on_event = on_event
        self._llm: LLMClient | None = None

    def _emit(self, event: str, payload: dict[str, Any]) -> None:
        if self.on_event:
            try:
                self.on_event(event, payload)
            except Exception:
                pass

    @property
    def llm(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMClient(self.settings, tools=[], agent="data_skew")
        return self._llm

    # -- static findings as a compact markdown list for the prompt ---------

    @staticmethod
    def _findings_for_prompt(report: SkewReport, lang: str) -> str:
        lines = []
        for f in report.findings:
            loc = dsk(lang, "rpt_line").format(n=f.line) if f.line else "-"
            lines.append(f"- [{f.severity.value}] {loc}: {f.description} → {f.suggestion}")
        return "\n".join(lines)

    # -- main entry ---------------------------------------------------------

    def analyze(
        self,
        sql: str,
        use_llm: bool = True,
        output_path: str | Path | None = None,
        on_text_delta: Callable[[str], None] | None = None,
        probe_context: str = "",
    ) -> SkewAnalysisResult:
        sql = (sql or "").strip()
        if not sql:
            raise ValueError("empty SQL")

        self._emit("static_scan_start", {"dialect": self.dialect})
        report = static_skew_report(sql, self.dialect, self.lang)
        self._emit("static_scan_done", {"findings": len(report.findings)})

        if not use_llm:
            return SkewAnalysisResult(
                report=report,
                markdown=render_report(report, self.lang),
                used_llm=False,
            )

        findings_md = self._findings_for_prompt(report, self.lang)
        if probe_context.strip():
            if self.lang == "zh":
                head = (
                    "【实测键值分布（来自用户数据库探查）】\n"
                    "以下分布来自真实数据，可信度高于静态推测。请针对列出的热点值做精准改写：\n"
                    "- 热点键隔离：对列出的热点值走独立分支（小表侧可 MAPJOIN/BROADCAST），"
                    "其余键正常 JOIN，最后 UNION ALL 合并；\n"
                    "- NULL 占比高的关联键：先过滤 NULL 再 UNION ALL 回来，或物化盐值列；\n"
                    "- 按实测 top1 占比选择加盐系数 N（如 top1≈35% 时 N 取 10~20）。"
                )
            else:
                head = (
                    "[Measured key distributions (probed from the user's database)]\n"
                    "These are real measurements — trust them over static guesses. "
                    "Rewrite specifically for the listed hot values:\n"
                    "- Isolate hot keys: route the listed hot values through a dedicated "
                    "branch (MAPJOIN/BROADCAST where the other side is small), join the "
                    "rest normally, then UNION ALL;\n"
                    "- For NULL-heavy join keys: filter NULLs first and UNION ALL them "
                    "back, or materialize a salt column;\n"
                    "- Pick the salting factor N from the measured top1 share "
                    "(e.g. N=10–20 for top1≈35%)."
                )
            findings_md = f"{findings_md}\n\n{head}\n{probe_context.strip()}"
        system = build_system_prompt(self.dialect, self.lang, findings_md)
        user = build_user_prompt(sql, self.lang)
        self._emit("llm_start", {})
        resp = self.llm.chat(
            system_prompt=system,
            messages=[{"role": "user", "content": user}],
            on_text_delta=on_text_delta,
        )
        reply = resp.reply_text or ""
        self._emit("llm_done", {"chars": len(reply)})

        optimized = extract_optimized_sql(reply)
        report.optimized_sql = optimized
        report.consistency_notes = _consistency_notes(reply)
        report.findings.extend(parse_optimization_table(reply))

        if optimized:
            out = self._write_optimized(optimized, output_path)
            if out:
                report.output_file = str(out)

        return SkewAnalysisResult(
            report=report,
            markdown=render_report(report, self.lang),
            llm_raw=reply,
            used_llm=True,
        )

    @staticmethod
    def _write_optimized(optimized_sql: str, output_path: str | Path | None) -> Path | None:
        try:
            path = Path(output_path) if output_path else Path(DEFAULT_OUTPUT_NAME)
            if path.suffix.lower() != ".sql":
                path = path.with_suffix(".sql")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(optimized_sql.rstrip() + "\n", encoding="utf-8")
            return path
        except OSError:
            return None
