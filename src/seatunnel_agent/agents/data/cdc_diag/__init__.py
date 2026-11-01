"""CDC 同步异常诊断 — 同步快照 → binlog/断点/丢数风险发现.

Deterministic core: compare the consumer's binlog coordinates against
the source (files behind, byte lag, a consumer ahead of the source —
the broken-resume smell), judge event staleness, estimate the
binlog-retention data-loss risk, and classify the pasted errors —
each finding with evidence and a prescription.  No database
connection.
"""

from .diagnoser import (
    CdcDiagnosis,
    CdcFinding,
    diagnose_cdc,
    parse_cdc_snapshot,
)
from .report import render_markdown

__all__ = [
    "CdcDiagnosis",
    "CdcFinding",
    "diagnose_cdc",
    "parse_cdc_snapshot",
    "render_markdown",
]
