"""Baseline file support: suppress known findings, fail only on new ones.

The baseline is a JSON file of finding fingerprints. ``--update-baseline``
records the current findings; subsequent reviews with ``--baseline`` only
report findings whose fingerprint is not in the file.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .report import Finding

DEFAULT_BASELINE = ".sqlreview-baseline.json"


def _fingerprint(label: str, finding: Finding) -> str:
    label = label.replace("\\", "/")  # same fingerprint on Windows and POSIX
    key = f"{label}|{finding.category}|{finding.description}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def save_baseline(
    path: str | Path, entries: list[tuple[str, Finding]]
) -> int:
    """Write fingerprints of *(source label, finding)* pairs; returns count."""
    prints = sorted({_fingerprint(label, f) for label, f in entries})
    doc = {"version": 1, "findings": prints}
    Path(path).write_text(
        json.dumps(doc, indent=2) + "\n", encoding="utf-8"
    )
    return len(prints)


def load_baseline(path: str | Path) -> set[str]:
    file = Path(path)
    if not file.is_file():
        raise ValueError(f"基线文件不存在: {file}")
    try:
        doc = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"基线文件解析失败 ({file}): {exc}") from exc
    if not isinstance(doc, dict) or not isinstance(doc.get("findings"), list):
        raise ValueError(f"基线文件格式无效: {file}")
    return {fp for fp in doc["findings"] if isinstance(fp, str)}


def split_by_baseline(
    label: str, findings: list[Finding], baseline: set[str]
) -> tuple[list[Finding], list[Finding]]:
    """Return ``(new, known)`` findings for one source."""
    new: list[Finding] = []
    known: list[Finding] = []
    for f in findings:
        (known if _fingerprint(label, f) in baseline else new).append(f)
    return new, known
