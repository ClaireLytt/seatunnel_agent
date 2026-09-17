"""Data quality checks on query results — pure Python analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_NULL_THRESHOLD = 0.5
_OUTLIER_SIGMA = 3.0
_MAX_ROWS_FOR_ANALYSIS = 10000


@dataclass
class QualityWarning:
    column: str
    warning_type: str  # "high_null", "constant", "outlier", "duplicate_rows"
    detail: str


@dataclass
class QualityReport:
    warnings: list[QualityWarning] = field(default_factory=list)
    row_count: int = 0
    duplicate_count: int = 0

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)


def _is_numeric(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _mean_stddev(values: list[float]) -> tuple[float, float]:
    n = len(values)
    if n < 2:
        return (values[0] if values else 0.0, 0.0)
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    return mean, variance ** 0.5


def _check_nulls(columns: list[str], rows: list[tuple]) -> list[QualityWarning]:
    warnings: list[QualityWarning] = []
    if not rows:
        return warnings
    n = len(rows)
    for i, col in enumerate(columns):
        null_count = sum(1 for r in rows if r[i] is None)
        pct = null_count / n
        if pct > _NULL_THRESHOLD:
            warnings.append(QualityWarning(
                column=col,
                warning_type="high_null",
                detail=f"{null_count}/{n} ({pct:.0%})",
            ))
    return warnings


def _check_constant(columns: list[str], rows: list[tuple]) -> list[QualityWarning]:
    warnings: list[QualityWarning] = []
    if len(rows) < 2:
        return warnings
    for i, col in enumerate(columns):
        vals = {r[i] for r in rows}
        if len(vals) == 1:
            v = next(iter(vals))
            warnings.append(QualityWarning(
                column=col,
                warning_type="constant",
                detail=f"all = {v!r}" if v is not None else "all NULL",
            ))
    return warnings


def _check_outliers(columns: list[str], rows: list[tuple]) -> list[QualityWarning]:
    warnings: list[QualityWarning] = []
    if len(rows) < 3:
        return warnings
    for i, col in enumerate(columns):
        nums = [float(r[i]) for r in rows if _is_numeric(r[i])]
        if len(nums) < 3:
            continue
        mean, sd = _mean_stddev(nums)
        if sd == 0:
            continue
        lo, hi = mean - _OUTLIER_SIGMA * sd, mean + _OUTLIER_SIGMA * sd
        outliers = [v for v in nums if v < lo or v > hi]
        if outliers:
            warnings.append(QualityWarning(
                column=col,
                warning_type="outlier",
                detail=f"{len(outliers)} value(s) outside [{lo:.2f}, {hi:.2f}]",
            ))
    return warnings


def _check_duplicates(rows: list[tuple]) -> int:
    if not rows:
        return 0
    seen: set[tuple] = set()
    dup_count = 0
    for r in rows:
        if r in seen:
            dup_count += 1
        else:
            seen.add(r)
    return dup_count


def check_quality(columns: list[str], rows: list[tuple]) -> QualityReport:
    """Analyse query result data for quality issues."""
    analysis_rows = rows[:_MAX_ROWS_FOR_ANALYSIS]
    warnings: list[QualityWarning] = []
    warnings.extend(_check_nulls(columns, analysis_rows))
    warnings.extend(_check_constant(columns, analysis_rows))
    warnings.extend(_check_outliers(columns, analysis_rows))
    dup_count = _check_duplicates(analysis_rows)
    if dup_count:
        warnings.append(QualityWarning(
            column="",
            warning_type="duplicate_rows",
            detail=f"{dup_count} duplicate row(s)",
        ))
    return QualityReport(
        warnings=warnings,
        row_count=len(rows),
        duplicate_count=dup_count,
    )
