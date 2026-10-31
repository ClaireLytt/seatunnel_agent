"""Kafka 消费积压诊断 — 消费组快照 → 发现与追赶 ETA.

Deterministic core: parse one consumer group's offset snapshot (JSON or
CSV; rates optional) and fire rules for the total backlog, hot
partitions far above the median lag, partitions consuming slower than
they produce, stalled partitions and slow catch-up ETAs — each with
evidence and a prescription.  No broker connection.
"""

from .analyzer import (
    KafkaFinding,
    LagResult,
    PartitionLag,
    analyze_lag,
    parse_lag_snapshot,
)
from .report import render_markdown

__all__ = [
    "KafkaFinding",
    "LagResult",
    "PartitionLag",
    "analyze_lag",
    "parse_lag_snapshot",
    "render_markdown",
]
