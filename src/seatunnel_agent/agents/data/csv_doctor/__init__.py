"""CSV 急救 — 坏文件 → 字节取证 + 结构修复 + 可用的 CSV.

Deterministic core: byte-level forensics (BOM, control characters,
U+FFFD losses, double-encoded mojibake recovered with before/after
samples) plus structural repair (delimiter sniffing, ragged rows padded
or merged, duplicate headers suffixed) — the repaired CSV round-trips
through sample_profile's parser so every rows-eating agent here can
consume it.  No database connection.
"""

from .doctor import CsvDoctorReport, CsvFinding, diagnose_csv
from .report import render_markdown

__all__ = [
    "CsvDoctorReport",
    "CsvFinding",
    "diagnose_csv",
    "render_markdown",
]
