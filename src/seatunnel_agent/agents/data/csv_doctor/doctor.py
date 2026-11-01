"""Deterministic triage and repair for a broken CSV.

Every rows-eating agent in this workspace assumes a clean CSV; this one
exists for the file that will not parse or arrives as mojibake.  Paste
the raw text and the doctor runs byte-level forensics plus structural
repair, emitting a **fixed CSV** that ``sample_profile.parse_rows``
accepts (the round-trip guard):

* CD001 low — a BOM at the start (stripped);
* CD002 — ragged rows whose width differs from the modal width (short
  rows padded, overflow merged into the last field; medium, high from
  20% of rows);
* CD003 medium — lines with unbalanced quotes (reported, parsed
  leniently);
* CD004 high — U+FFFD replacement characters: those bytes are already
  lost, no repair can bring them back;
* CD005 medium — recoverable double-encoded text (UTF-8 read as
  cp1252/latin-1, the classic ``ä¸­æ–‡`` mojibake) — repaired, with a
  before/after sample;
* CD006 low — control characters (stripped);
* CD007 medium — duplicate header names (suffixed ``_2``, ``_3`` …).

The delimiter is sniffed from ``, ; | tab`` by column-count
consistency.  Deterministic — same text in, same diagnosis and fix out.
"""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from seatunnel_agent.common.severity import severity_counts

__all__ = ["CsvDoctorReport", "CsvFinding", "diagnose_csv"]

_DELIMS = [",", ";", "|", "\t"]
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_MOJI_RE = re.compile(r"[Â-Ãä-æè-ê][\u0080-ÿ–—‘’“”…Œœˆ‰ŠšŽžƒ†‡•€™]")
_RAGGED_HIGH = 0.20


@dataclass
class CsvFinding:
    code: str            # CD001..CD007
    severity: str        # high | medium | low
    count: int = 0
    sample: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "severity": self.severity,
                "count": self.count, "sample": self.sample}


@dataclass
class CsvDoctorReport:
    delimiter: str
    rows: int = 0
    columns: int = 0
    findings: list[CsvFinding] = field(default_factory=list)
    fixed_csv: str = ""

    @property
    def clean(self) -> bool:
        return not self.findings

    def counts(self) -> dict[str, int]:
        return severity_counts(self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {"delimiter": self.delimiter, "rows": self.rows,
                "columns": self.columns, "clean": self.clean,
                "counts": self.counts(),
                "findings": [f.to_dict() for f in self.findings],
                "fixed_csv": self.fixed_csv}


def _recover_mojibake(text: str) -> tuple[str, int, str]:
    """Undo UTF-8-read-as-cp1252 line by line; returns (text, lines, sample)."""
    out_lines = []
    repaired = 0
    sample = ""
    for line in text.splitlines():
        if _MOJI_RE.search(line):
            for codec in ("cp1252", "latin-1"):
                try:
                    candidate = line.encode(codec).decode("utf-8")
                except (UnicodeEncodeError, UnicodeDecodeError):
                    continue
                repaired += 1
                if not sample:
                    sample = f"{line[:30]} -> {candidate[:30]}"
                line = candidate
                break
        out_lines.append(line)
    return "\n".join(out_lines), repaired, sample


def _sniff_delimiter(lines: list[str]) -> str:
    best, best_score = ",", -1.0
    for cand in _DELIMS:
        widths = [len(next(csv.reader([ln], delimiter=cand), []))
                  for ln in lines[:50]]
        widths = [w for w in widths if w]
        if not widths:
            continue
        modal, hits = Counter(widths).most_common(1)[0]
        if modal < 2:
            continue
        score = hits / len(widths) + modal / 1000
        if score > best_score:
            best, best_score = cand, score
    return best


def diagnose_csv(text: str) -> CsvDoctorReport:
    """Raw CSV text → diagnosis + a fixed CSV that parse_rows accepts."""
    if not (text or "").strip():
        raise ValueError("the CSV text must not be empty")
    findings: list[CsvFinding] = []

    if text.startswith("﻿"):
        text = text.lstrip("﻿")
        findings.append(CsvFinding("CD001", "low", 1, "UTF-8 BOM"))

    lost = text.count("�")
    if lost:
        findings.append(CsvFinding("CD004", "high", lost, "U+FFFD"))

    text, repaired, moji_sample = _recover_mojibake(text)
    if repaired:
        findings.append(CsvFinding("CD005", "medium", repaired,
                                   moji_sample))

    ctrl = len(_CTRL_RE.findall(text))
    if ctrl:
        text = _CTRL_RE.sub("", text)
        findings.append(CsvFinding("CD006", "low", ctrl, ""))

    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        raise ValueError("need a header line and at least one data row")
    delim = _sniff_delimiter(lines)

    unbalanced = [i + 1 for i, ln in enumerate(lines)
                  if ln.count('"') % 2 == 1]
    if unbalanced:
        shown = ", ".join(str(n) for n in unbalanced[:5])
        findings.append(CsvFinding("CD003", "medium", len(unbalanced),
                                   f"line(s) {shown}"))

    parsed = [next(csv.reader([ln], delimiter=delim), [])
              for ln in lines]
    modal = Counter(len(r) for r in parsed).most_common(1)[0][0]

    header = [c.strip() for c in parsed[0]]
    seen: Counter[str] = Counter()
    fixed_header = []
    dupes = 0
    for col in header:
        seen[col] += 1
        if seen[col] > 1:
            dupes += 1
            fixed_header.append(f"{col}_{seen[col]}")
        else:
            fixed_header.append(col)
    if dupes:
        findings.append(CsvFinding("CD007", "medium", dupes,
                                   ", ".join(sorted(
                                       c for c, n in seen.items()
                                       if n > 1))))

    ragged_lines = []
    fixed_rows: list[list[str]] = []
    for i, row in enumerate(parsed[1:], start=2):
        if len(row) != modal:
            ragged_lines.append(i)
        if len(row) < modal:
            row = row + [""] * (modal - len(row))
        elif len(row) > modal:
            row = row[:modal - 1] + [delim.join(row[modal - 1:])]
        fixed_rows.append(row)
    if ragged_lines:
        share = len(ragged_lines) / max(len(parsed) - 1, 1)
        shown = ", ".join(str(n) for n in ragged_lines[:5])
        findings.append(CsvFinding(
            "CD002", "high" if share >= _RAGGED_HIGH else "medium",
            len(ragged_lines), f"line(s) {shown}"))

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(fixed_header[:modal]
                    + [f"col_{k + 1}" for k in
                       range(modal - len(fixed_header))])
    writer.writerows(fixed_rows)
    fixed_csv = buf.getvalue()

    # round-trip guard: the repaired file must feed the family's parser
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    headers, rows = parse_rows(fixed_csv)
    if len(headers) != modal or len(rows) != len(fixed_rows):
        raise ValueError("internal: the repaired CSV failed to round-trip")

    order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: (order[f.severity], f.code))
    return CsvDoctorReport(delimiter=delim, rows=len(fixed_rows),
                           columns=modal, findings=findings,
                           fixed_csv=fixed_csv)
