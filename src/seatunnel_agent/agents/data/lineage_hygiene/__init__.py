"""Warehouse hygiene — lineage-driven dead-weight report.

Three questions nobody else in the suite answers:

* **orphan outputs** — tables that are written but never read downstream;
* **dead columns** — DDL columns of tables that *do* have readers, yet the
  column itself is never selected by any downstream edge;
* **dangling definitions** — tables defined in DDL that appear in no
  lineage edge at all.

datadict documents what exists, impact answers what a change would break;
hygiene answers what could be retired. Fully deterministic — built on the
existing LineageGraph, no database, no LLM.
"""

from .analyzer import HygieneReport, analyze_dir, analyze_sql_text
from .report import render_markdown

__all__ = [
    "HygieneReport",
    "analyze_dir",
    "analyze_sql_text",
    "render_markdown",
]
