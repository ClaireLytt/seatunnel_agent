# -*- coding: utf-8 -*-
"""Target-side CREATE TABLE renderers (Doris / StarRocks / Hive).

Key-model policy: an explicit PRIMARY KEY becomes UNIQUE KEY (Doris) /
PRIMARY KEY (StarRocks); without one we fall back to DUPLICATE KEY on the
first key-compatible column and record a warning — never guess a unique
key, a wrong one silently deduplicates data.
"""

from __future__ import annotations

from .model import TableSpec
from .typemap import enum_values, map_type

# Doris/StarRocks 的 key 列不允许这些类型
_NON_KEY_TYPES = ("STRING", "JSON", "FLOAT", "DOUBLE", "BOOLEAN")


def _dq(s: str) -> str:
    """Escape for a double-quoted Doris/StarRocks string literal."""
    return (s or "").replace("\\", "\\\\").replace('"', '\\"')


def _sq(s: str) -> str:
    """Escape for a single-quoted Hive string literal."""
    return (s or "").replace("\\", "\\\\").replace("'", "\\'")


def _col_comment(col) -> str:
    """Column comment, with enum/set allowed values appended."""
    values = enum_values(col.mysql_type)
    comment = col.comment or ""
    if values:
        allowed = "取值: " + "/".join(values)
        comment = f"{comment} ({allowed})" if comment else allowed
    return comment


def _is_key_compatible(mapped: str) -> bool:
    return not any(mapped.startswith(t) for t in _NON_KEY_TYPES)


def render_ddl(spec: TableSpec, target: str) -> tuple[str, list[str]]:
    """One CREATE TABLE for *spec* on *target*; returns (ddl, warnings)."""
    if target == "hive":
        return _render_hive(spec)
    if target in ("doris", "starrocks"):
        return _render_olap(spec, target)
    raise ValueError(f"不支持的目标类型: {target}")


# ---------------------------------------------------------------------------
# Doris / StarRocks
# ---------------------------------------------------------------------------

def _render_olap(spec: TableSpec, target: str) -> tuple[str, list[str]]:
    warnings: list[str] = []
    mapped = {c.name: map_type(c.mysql_type, target)[0] for c in spec.columns}

    key_cols = [k for k in spec.primary_keys if k in mapped]
    key_kind = "UNIQUE KEY" if target == "doris" else "PRIMARY KEY"
    if not key_cols:
        # 无主键：退化为 DUPLICATE KEY，选第一个 key 兼容列
        key_kind = "DUPLICATE KEY"
        first = next((c.name for c in spec.columns
                      if _is_key_compatible(mapped[c.name])), None)
        if first is None:
            first = spec.columns[0].name
            warnings.append(
                f"{spec.full_name}: 没有任何 key 兼容列，DUPLICATE KEY 使用 "
                f"{first}（类型 {mapped[first]}），建表可能失败，请人工调整")
        else:
            warnings.append(
                f"{spec.full_name}: 源表无主键，退化为 DUPLICATE KEY({first})，"
                "数据不去重")
        key_cols = [first]
    else:
        bad = [k for k in key_cols if not _is_key_compatible(mapped[k])]
        for k in bad:
            warnings.append(
                f"{spec.full_name}: 主键列 {k} 映射类型 {mapped[k]} "
                "不能作为 key 列，请人工调整")

    # key 列必须排在最前（Doris/StarRocks 要求）
    ordered = ([c for k in key_cols for c in spec.columns if c.name == k]
               + [c for c in spec.columns if c.name not in key_cols])

    lines = []
    for col in ordered:
        col_type, warn = map_type(col.mysql_type, target)
        if warn:
            warnings.append(f"{spec.full_name}.{col.name}: {warn}")
        not_null = " NOT NULL" if (col.name in key_cols or not col.nullable) else ""
        comment = _col_comment(col)
        comment_sql = f' COMMENT "{_dq(comment)}"' if comment else ""
        lines.append(f"  `{col.name}` {col_type}{not_null}{comment_sql}")

    key_list = ", ".join(f"`{k}`" for k in key_cols)
    buckets = "BUCKETS AUTO" if target == "doris" else "BUCKETS 8"
    table_comment = (f'\nCOMMENT "{_dq(spec.comment)}"' if spec.comment else "")
    engine = "\nENGINE = OLAP" if target == "doris" else ""
    ddl = (
        f"CREATE TABLE IF NOT EXISTS `{spec.database or 'ods'}`.`{spec.name}` (\n"
        + ",\n".join(lines)
        + f"\n){engine}\n{key_kind}({key_list})"
        + table_comment
        + f"\nDISTRIBUTED BY HASH({key_list}) {buckets}"
        + '\nPROPERTIES (\n  "replication_num" = "1"\n);\n'
    )
    return ddl, warnings


# ---------------------------------------------------------------------------
# Hive
# ---------------------------------------------------------------------------

def _render_hive(spec: TableSpec) -> tuple[str, list[str]]:
    warnings: list[str] = []
    lines = []
    for col in spec.columns:
        col_type, warn = map_type(col.mysql_type, "hive")
        if warn:
            warnings.append(f"{spec.full_name}.{col.name}: {warn}")
        comment = _col_comment(col)
        comment_sql = f" COMMENT '{_sq(comment)}'" if comment else ""
        lines.append(f"  `{col.name}` {col_type}{comment_sql}")
    table_comment = (f"\nCOMMENT '{_sq(spec.comment)}'" if spec.comment else "")
    ddl = (
        f"CREATE TABLE IF NOT EXISTS `{spec.database or 'ods'}`.`{spec.name}` (\n"
        + ",\n".join(lines)
        + f"\n){table_comment}\nSTORED AS ORC;\n"
    )
    return ddl, warnings
