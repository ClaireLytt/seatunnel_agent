"""Result dataclasses for the data comparison engine.

Moved verbatim out of comparator.py; comparator re-exports every name so
existing imports keep working.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SchemaDiffItem:
    column: str
    status: str  # "added", "removed", "type_changed"
    type_a: str = ""
    type_b: str = ""


@dataclass
class SchemaDiffResult:
    table_a: str
    table_b: str
    items: list[SchemaDiffItem] = field(default_factory=list)
    cols_only_a: int = 0
    cols_only_b: int = 0
    type_changes: int = 0

    @property
    def has_changes(self) -> bool:
        return bool(self.items)


@dataclass
class RowCountResult:
    table_a: str
    count_a: int
    table_b: str
    count_b: int
    delta: int = 0
    delta_pct: float = 0.0


@dataclass
class AggregateItem:
    column: str
    metric: str  # "sum", "avg", "min", "max", "null_count"
    value_a: Any = None
    value_b: Any = None
    match: bool = True


@dataclass
class AggregateResult:
    table_a: str
    table_b: str
    items: list[AggregateItem] = field(default_factory=list)
    mismatches: int = 0


@dataclass
class ModifiedRow:
    key: tuple
    changes: list[tuple[str, Any, Any]]  # (column, old_val, new_val)
    row_a: tuple | None = None
    row_b: tuple | None = None


@dataclass
class KeyedDiffResult:
    key_columns: list[str]
    columns: list[str]
    added: list[tuple] = field(default_factory=list)
    removed: list[tuple] = field(default_factory=list)
    modified: list[ModifiedRow] = field(default_factory=list)


@dataclass
class ProfileItem:
    column: str
    distinct_a: int = 0
    distinct_b: int = 0
    null_rate_a: float = 0.0
    null_rate_b: float = 0.0
    min_a: Any = None
    min_b: Any = None
    max_a: Any = None
    max_b: Any = None


@dataclass
class ProfileResult:
    table_a: str
    table_b: str
    total_a: int = 0
    total_b: int = 0
    items: list[ProfileItem] = field(default_factory=list)


@dataclass
class ThresholdConfig:
    value: float
    is_percentage: bool = True


@dataclass
class BatchFullItem:
    table_a: str
    table_b: str
    schema: SchemaDiffResult | None = None
    row_count: RowCountResult | None = None
    aggregate: AggregateResult | None = None
    has_diffs: bool = False


ColumnMapping = dict[str, str]


@dataclass
class QualityRule:
    column: str
    rule_type: str  # "not_null_rate", "unique_rate", "min_value", "max_value", "value_range", "expression"
    threshold: float = 0.0
    min_val: float | None = None
    max_val: float | None = None
    expression: str = ""


@dataclass
class QualityResult:
    rule: QualityRule
    actual_value: float
    passed: bool
    pending: bool = False


@dataclass
class ReportDiffItem:
    section: str
    field: str
    old_value: Any
    new_value: Any
    changed: bool


@dataclass
class ReportDiff:
    items: list[ReportDiffItem] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return any(i.changed for i in self.items)


@dataclass
class SkewBucket:
    value: str
    count_a: int = 0
    count_b: int = 0
    pct_a: float = 0.0
    pct_b: float = 0.0


@dataclass
class SkewItem:
    column: str
    gini_a: float = 0.0
    gini_b: float = 0.0
    cv_a: float = 0.0
    cv_b: float = 0.0
    top1_pct_a: float = 0.0
    top1_pct_b: float = 0.0
    ndv_a: int = 0
    ndv_b: int = 0
    buckets: list[SkewBucket] = field(default_factory=list)


@dataclass
class SkewResult:
    table_a: str
    table_b: str
    total_a: int = 0
    total_b: int = 0
    items: list[SkewItem] = field(default_factory=list)


@dataclass
class ChecksumItem:
    segment: int
    checksum_a: str
    checksum_b: str
    match: bool = True


@dataclass
class ChecksumResult:
    table_a: str
    table_b: str
    items: list[ChecksumItem] = field(default_factory=list)
    match_count: int = 0
    mismatch_count: int = 0


@dataclass
class PartitionCompareItem:
    partition_value: str
    count_a: int = 0
    count_b: int = 0
    delta: int = 0
    delta_pct: float = 0.0


@dataclass
class PartitionResult:
    table_a: str
    table_b: str
    partition_column: str = ""
    items: list[PartitionCompareItem] = field(default_factory=list)
    total_delta: int = 0


@dataclass
class CustomAggItem:
    expression: str
    alias: str
    value_a: float | None = None
    value_b: float | None = None
    match: bool = True


@dataclass
class CustomAggResult:
    table_a: str
    table_b: str
    items: list[CustomAggItem] = field(default_factory=list)
    mismatches: int = 0


@dataclass
class CompareReport:
    """Structured comparison report — source of truth for export."""
    schema: SchemaDiffResult | None = None
    row_count: RowCountResult | None = None
    sample: Any | None = None  # ResultDiff from text2sql.differ
    aggregate: AggregateResult | None = None
    batch_counts: list[RowCountResult] | None = None
    profile: ProfileResult | None = None
    keyed_diff: KeyedDiffResult | None = None
    batch_full: list[BatchFullItem] | None = None
    skew: SkewResult | None = None
    checksum: ChecksumResult | None = None
    partition: PartitionResult | None = None
    custom_agg: CustomAggResult | None = None
    chunked: Any | None = None  # ChunkedResult (import cycle: see .chunked)
    elapsed_ms: int = 0

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict."""
        d = asdict(self)
        return json.loads(json.dumps(d, default=str))

    @staticmethod
    def _restore_items(data: dict | None, item_cls: type, container_cls: type):
        if not data:
            return None
        d = dict(data)
        items = [item_cls(**it) for it in d.pop("items", [])]
        return container_cls(**d, items=items)

    @classmethod
    def from_dict(cls, d: dict) -> CompareReport:
        """Reconstruct from a dict produced by ``to_dict``.

        Safe to call multiple times on the same dict — input is never mutated.
        """
        _ri = cls._restore_items

        schema = _ri(d.get("schema"), SchemaDiffItem, SchemaDiffResult)

        row_count = RowCountResult(**d["row_count"]) if d.get("row_count") else None

        aggregate = _ri(d.get("aggregate"), AggregateItem, AggregateResult)

        batch_counts = None
        if d.get("batch_counts"):
            batch_counts = [RowCountResult(**rc) for rc in d["batch_counts"]]

        profile = _ri(d.get("profile"), ProfileItem, ProfileResult)

        keyed_diff = None
        if d.get("keyed_diff"):
            kd = dict(d["keyed_diff"])
            mods = []
            for m in kd.pop("modified", []):
                mods.append(ModifiedRow(
                    key=tuple(m["key"]),
                    changes=[tuple(c) for c in m["changes"]],
                    row_a=tuple(m["row_a"]) if m.get("row_a") else None,
                    row_b=tuple(m["row_b"]) if m.get("row_b") else None,
                ))
            added = [tuple(r) for r in kd.pop("added", [])]
            removed = [tuple(r) for r in kd.pop("removed", [])]
            keyed_diff = KeyedDiffResult(
                **kd, added=added, removed=removed, modified=mods,
            )

        batch_full = None
        if d.get("batch_full"):
            batch_full = []
            for bf in d["batch_full"]:
                bf_schema = _ri(bf.get("schema"), SchemaDiffItem, SchemaDiffResult)
                bf_rc = RowCountResult(**bf["row_count"]) if bf.get("row_count") else None
                bf_agg = _ri(bf.get("aggregate"), AggregateItem, AggregateResult)
                batch_full.append(BatchFullItem(
                    table_a=bf["table_a"], table_b=bf["table_b"],
                    schema=bf_schema, row_count=bf_rc, aggregate=bf_agg,
                    has_diffs=bf.get("has_diffs", False),
                ))

        skew = None
        if d.get("skew"):
            sk = dict(d["skew"])
            sitems = []
            for si in sk.pop("items", []):
                si_d = dict(si)
                buckets = [SkewBucket(**b) for b in si_d.pop("buckets", [])]
                sitems.append(SkewItem(**si_d, buckets=buckets))
            skew = SkewResult(**sk, items=sitems)

        checksum = _ri(d.get("checksum"), ChecksumItem, ChecksumResult)
        partition = _ri(d.get("partition"), PartitionCompareItem, PartitionResult)
        custom_agg = _ri(d.get("custom_agg"), CustomAggItem, CustomAggResult)

        chunked = None
        if d.get("chunked"):
            from .chunked import ChunkedResult, ChunkMismatch
            cd = dict(d["chunked"])
            mism = [ChunkMismatch(**m) for m in cd.pop("mismatched", [])]
            chunked = ChunkedResult(**cd, mismatched=mism)

        sample = None
        if d.get("sample"):
            from seatunnel_agent.agents.data.text2sql.differ import ResultDiff
            sd = d["sample"]
            sample = ResultDiff(
                added_rows=[tuple(r) for r in sd.get("added_rows", [])],
                removed_rows=[tuple(r) for r in sd.get("removed_rows", [])],
                columns_added=list(sd.get("columns_added", [])),
                columns_removed=list(sd.get("columns_removed", [])),
                old_count=sd.get("old_count", 0),
                new_count=sd.get("new_count", 0),
            )

        return cls(
            schema=schema,
            row_count=row_count,
            sample=sample,
            aggregate=aggregate,
            batch_counts=batch_counts,
            profile=profile,
            keyed_diff=keyed_diff,
            batch_full=batch_full,
            skew=skew,
            checksum=checksum,
            partition=partition,
            custom_agg=custom_agg,
            chunked=chunked,
            elapsed_ms=d.get("elapsed_ms", 0),
        )


