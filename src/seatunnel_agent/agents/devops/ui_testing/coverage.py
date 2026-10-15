"""Manual-checklist coverage: which of the 75 checklist items are automated.

Parses ``examples/dc_test_checklist.html`` (the checklist data lives in a JS
``SECTIONS`` literal) and maps every item id onto the case library:

- ``auto``    — an automated case with the same id exists
- ``runner``  — no case needed: the framework itself performs this step
- ``manual``  — a case exists but is tagged ``manual`` (annotated why)
- ``missing`` — no case carries this id

Case ids that are not checklist items (SR group, A5b, B3a, ...) are reported
separately as "beyond the checklist".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .models import TestCase

CHECKLIST_PATH = Path("examples") / "dc_test_checklist.html"

_ITEM_RE = re.compile(r'\{id:"([A-Z]+\d*(?:-\d+)?)",\s*t:"(.*?)",\s*s:')
_SECTION_RE = re.compile(r'\{id:"([A-Z]+\d*)",\s*title:"(.*?)",\s*items:')

# Checklist prep items the runner itself performs on every run/case.
RUNNER_COVERED = {
    "P0-1": "runner 每轮种子 dc_test_* 十表进 SQLite",
    "P0-2": "runner 以子进程启动被测应用并探测就绪",
    "P0-3": "runner 每条用例默认切换中文界面",
}


@dataclass
class CoverageRow:
    item_id: str
    title: str
    status: str        # auto | manual | missing


@dataclass
class CoverageReport:
    rows: list[CoverageRow]
    extra_case_ids: list[str]      # automated cases beyond the checklist
    sections: dict[str, str]       # section id -> section title

    def counts(self) -> dict[str, int]:
        out = {"auto": 0, "runner": 0, "manual": 0, "missing": 0}
        for r in self.rows:
            out[r.status] += 1
        return out


def checklist_items(path: Path = CHECKLIST_PATH) -> tuple[list[tuple[str, str]], dict[str, str]]:
    """(item_id, title) pairs plus section titles; empty when absent."""
    if not path.is_file():
        return [], {}
    html = path.read_text(encoding="utf-8", errors="replace")
    i = html.find("const SECTIONS")
    if i < 0:
        return [], {}
    body = html[i:]
    sections = {m.group(1): m.group(2) for m in _SECTION_RE.finditer(body)}
    items = [(m.group(1), m.group(2)) for m in _ITEM_RE.finditer(body)
             if m.group(1) not in sections]
    return items, sections


def compute_coverage(cases: list[TestCase],
                     path: Path = CHECKLIST_PATH) -> CoverageReport | None:
    """None when the checklist file isn't available (e.g. sdist installs)."""
    items, sections = checklist_items(path)
    if not items:
        return None
    by_id = {c.id.upper(): c for c in cases}
    rows: list[CoverageRow] = []
    for item_id, title in items:
        case = by_id.get(item_id.upper())
        if item_id in RUNNER_COVERED:
            status = "runner"
        elif case is None:
            status = "missing"
        elif "manual" in case.tags:
            status = "manual"
        else:
            status = "auto"
        rows.append(CoverageRow(item_id, title, status))
    checklist_ids = {i.upper() for i, _ in items}
    extra = sorted(c.id for c in cases
                   if c.id.upper() not in checklist_ids and "manual" not in c.tags)
    return CoverageReport(rows=rows, extra_case_ids=extra, sections=sections)
