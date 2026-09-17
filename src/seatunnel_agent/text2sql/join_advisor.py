"""Smart JOIN recommendation — column name matching across tables."""

from __future__ import annotations

from dataclasses import dataclass

from .schema import SchemaStore

_NON_JOIN_COLUMNS = frozenset({
    "pt", "created_at", "updated_at", "create_time", "update_time",
    "status", "type", "name", "comment", "remark", "description",
    "is_deleted", "sort_order",
})

_EXACT_MATCH_EXCLUDE = _NON_JOIN_COLUMNS | {"id"}

_MAX_SUGGESTIONS = 10


@dataclass
class JoinSuggestion:
    table_a: str
    column_a: str
    table_b: str
    column_b: str
    confidence: float
    match_type: str  # "exact_name", "fk_pattern"


def _column_names(table) -> set[str]:
    return {c.name.lower() for c in table.columns}


def suggest_joins(table_name: str, store: SchemaStore) -> list[JoinSuggestion]:
    """Find potential JOIN relationships for a table against all others in the store."""
    target = store.get(table_name)
    if target is None:
        return []

    target_cols = _column_names(target)
    target_lower = target.name.lower()
    suggestions: list[JoinSuggestion] = []
    seen: set[tuple[str, str, str, str]] = set()

    for other_name in store.table_names:
        other = store.get(other_name)
        if other is None or other.full_name == target.full_name:
            continue

        other_cols = _column_names(other)
        other_lower = other.name.lower()

        for col in target_cols & other_cols:
            if col in _EXACT_MATCH_EXCLUDE:
                continue
            key = (target.full_name, col, other.full_name, col)
            if key not in seen:
                seen.add(key)
                suggestions.append(JoinSuggestion(
                    table_a=target.full_name,
                    column_a=col,
                    table_b=other.full_name,
                    column_b=col,
                    confidence=0.9,
                    match_type="exact_name",
                ))

        if "id" in target_cols:
            fk_candidates = {f"{target_lower}_id"}
            if target_lower.endswith("s"):
                fk_candidates.add(f"{target_lower[:-1]}_id")
            for fk_col in fk_candidates & other_cols:
                key = (target.full_name, "id", other.full_name, fk_col)
                if key not in seen:
                    seen.add(key)
                    suggestions.append(JoinSuggestion(
                        table_a=target.full_name,
                        column_a="id",
                        table_b=other.full_name,
                        column_b=fk_col,
                        confidence=0.85,
                        match_type="fk_pattern",
                    ))

        for col in target_cols:
            if col.endswith("_id") and col not in _NON_JOIN_COLUMNS:
                ref_name = col[:-3]
                ref_candidates = {ref_name, ref_name + "s"}
                if ref_candidates & {other_lower} and "id" in other_cols:
                    key = (target.full_name, col, other.full_name, "id")
                    if key not in seen:
                        seen.add(key)
                        suggestions.append(JoinSuggestion(
                            table_a=target.full_name,
                            column_a=col,
                            table_b=other.full_name,
                            column_b="id",
                            confidence=0.85,
                            match_type="fk_pattern",
                        ))

    suggestions.sort(key=lambda s: (-s.confidence, s.table_b))
    return suggestions[:_MAX_SUGGESTIONS]
