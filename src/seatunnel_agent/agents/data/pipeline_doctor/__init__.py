"""Pipeline 故障诊断 — Spark/Hive/SeaTunnel 失败日志的根因定位与修复建议.

Deterministic core: reuse log_inspect's exception extraction, detect the
engine, match each cluster against a failure-signature knowledge base and
rank the findings into a diagnosis. The LLM only adds optional advice.
"""

from .diagnoser import Diagnosis, Finding, diagnose_dir, diagnose_files, diagnose_text
from .report import diagnosis_to_dict, render_diff_markdown, render_markdown
from .rundiff import RunDiff, diff_dirs, diff_reports, diff_texts

__all__ = [
    "Diagnosis",
    "Finding",
    "RunDiff",
    "diagnose_dir",
    "diagnose_files",
    "diagnose_text",
    "diagnosis_to_dict",
    "diff_dirs",
    "diff_reports",
    "diff_texts",
    "render_diff_markdown",
    "render_markdown",
]
