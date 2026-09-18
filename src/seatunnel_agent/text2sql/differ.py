"""Query result diff — compare two result sets."""

from __future__ import annotations

from dataclasses import dataclass, field

_MAX_DIFF_ROWS = 200


@dataclass
class ResultDiff:
    added_rows: list[tuple] = field(default_factory=list)
    removed_rows: list[tuple] = field(default_factory=list)
    columns_added: list[str] = field(default_factory=list)
    columns_removed: list[str] = field(default_factory=list)
    old_count: int = 0
    new_count: int = 0

    @property
    def has_changes(self) -> bool:
        return bool(
            self.added_rows or self.removed_rows
            or self.columns_added or self.columns_removed
        )


def diff_results(
    old_cols: list[str],
    old_rows: list[tuple],
    new_cols: list[str],
    new_rows: list[tuple],
) -> ResultDiff:
    """Compare two query results by columns and row values."""
    old_set = set(old_cols)
    new_set = set(new_cols)
    cols_added = [c for c in new_cols if c not in old_set]
    cols_removed = [c for c in old_cols if c not in new_set]

    shared = [c for c in old_cols if c in new_set]

    if shared:
        old_idx = [old_cols.index(c) for c in shared]
        new_idx = [new_cols.index(c) for c in shared]
        old_tuples = {tuple(r[i] for i in old_idx) for r in old_rows}
        new_tuples = {tuple(r[i] for i in new_idx) for r in new_rows}
        # 行内可能混有 None/数字/字符串，直接比较会 TypeError，按 repr 排序
        added = sorted(new_tuples - old_tuples, key=repr)[:_MAX_DIFF_ROWS]
        removed = sorted(old_tuples - new_tuples, key=repr)[:_MAX_DIFF_ROWS]
    else:
        added = [tuple(r) for r in new_rows[:_MAX_DIFF_ROWS]]
        removed = [tuple(r) for r in old_rows[:_MAX_DIFF_ROWS]]

    return ResultDiff(
        added_rows=added,
        removed_rows=removed,
        columns_added=cols_added,
        columns_removed=cols_removed,
        old_count=len(old_rows),
        new_count=len(new_rows),
    )
