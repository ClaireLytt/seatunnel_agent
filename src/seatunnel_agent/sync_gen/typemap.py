# -*- coding: utf-8 -*-
"""MySQL → Doris / StarRocks / Hive column type mapping.

``map_type`` is deterministic and total: every input maps to something,
and anything lossy or unknown carries a warning string. Unknown types
map to STRING with a warning prefixed ``unmapped_type`` — that prefix
drives the ``--fail-on unmapped`` CI gate.
"""

from __future__ import annotations

import re

TARGETS = ("doris", "starrocks", "hive")
UNMAPPED_PREFIX = "unmapped_type"

# Doris/StarRocks VARCHAR length is in bytes; MySQL in characters (utf8mb4
# = up to 4 bytes/char). 65533 is the Doris VARCHAR max.
_VARCHAR_MAX = 65533
_CHAR_FACTOR = 4

_TYPE_RE = re.compile(r"^\s*([a-z_]+)\s*(?:\(([^)]*)\))?\s*(.*)$")

_INT_MAP = {"tinyint": "TINYINT", "smallint": "SMALLINT",
            "mediumint": "INT", "int": "INT", "integer": "INT",
            "bigint": "BIGINT"}
# unsigned 放大一级，防溢出
_UNSIGNED_WIDEN = {"tinyint": "SMALLINT", "smallint": "INT",
                   "mediumint": "INT", "int": "BIGINT", "integer": "BIGINT"}

_TEXT_TYPES = {"text", "tinytext", "mediumtext", "longtext"}
_BINARY_TYPES = {"blob", "tinyblob", "mediumblob", "longblob",
                 "binary", "varbinary"}


def parse_mysql_type(raw: str) -> tuple[str, str, bool]:
    """``'decimal(12, 2) unsigned'`` → ``('decimal', '12, 2', True)``."""
    m = _TYPE_RE.match((raw or "").strip().lower())
    if not m:
        return (raw or "").strip().lower(), "", False
    base, params, rest = m.group(1), m.group(2) or "", m.group(3) or ""
    return base, params.strip(), "unsigned" in rest


def enum_values(raw: str) -> list[str] | None:
    """Allowed literals of an enum/set type, or None for other types."""
    base, params, _ = parse_mysql_type(raw)
    if base not in ("enum", "set") or not params:
        return None
    return re.findall(r"'((?:[^'\\]|\\.)*)'", params)


def map_type(mysql_type: str, target: str) -> tuple[str, str | None]:
    """Map one raw MySQL type to *target*; returns ``(type, warning|None)``."""
    base, params, unsigned = parse_mysql_type(mysql_type)
    hive = target == "hive"

    # --- boolean special cases (before the int rules) ---
    if base == "tinyint" and params == "1":
        return "BOOLEAN", None
    if base == "bit":
        if params in ("", "1"):
            return "BOOLEAN", None
        return "BIGINT", f"bit({params}) 映射为 BIGINT，按位语义丢失"

    # --- integers ---
    if base in _INT_MAP:
        if unsigned:
            if base == "bigint":
                if hive:
                    return ("DECIMAL(20,0)",
                            "bigint unsigned 超出 BIGINT 范围，映射为 DECIMAL(20,0)")
                return ("LARGEINT",
                        "bigint unsigned 超出 BIGINT 范围，映射为 LARGEINT")
            return _UNSIGNED_WIDEN[base], None
        return _INT_MAP[base], None

    # --- decimal ---
    if base in ("decimal", "numeric"):
        p, s = 10, 0
        if params:
            nums = [int(x) for x in re.findall(r"\d+", params)]
            if nums:
                p = nums[0]
                s = nums[1] if len(nums) > 1 else 0
        if p > 38:
            return f"DECIMAL(38,{min(s, 38)})", f"decimal({p},{s}) 精度超 38，已截断"
        return f"DECIMAL({p},{s})", None

    if base in ("float", "real"):
        return "FLOAT", None
    if base == "double":
        return "DOUBLE", None

    # --- strings ---
    if base in ("char", "varchar"):
        if hive:
            return "STRING", None
        if not params or not params.isdigit():
            return "STRING", None
        n = int(params) * _CHAR_FACTOR
        if n > _VARCHAR_MAX:
            return "STRING", f"{base}({params}) ×4 字节超 {_VARCHAR_MAX}，映射为 STRING"
        return f"VARCHAR({n})", None
    if base in _TEXT_TYPES:
        return "STRING", None
    if base in _BINARY_TYPES:
        if hive:
            return "BINARY", None
        return "STRING", f"{base} 二进制数据经 Jdbc→OLAP 可能有损，映射为 STRING"

    # --- temporal ---
    if base == "date":
        return "DATE", None
    if base in ("datetime", "timestamp"):
        if hive:
            return "TIMESTAMP", None
        if target == "doris" and params.isdigit():
            return f"DATETIME({min(int(params), 6)})", None
        return "DATETIME", None
    if base == "time":
        return "STRING", "目标端无 TIME 类型，映射为 STRING"
    if base == "year":
        return "SMALLINT", None

    # --- enum / set ---
    if base in ("enum", "set"):
        if hive:
            return "STRING", None
        values = enum_values(mysql_type) or []
        longest = max((len(v) for v in values), default=16)
        n = min(max(longest * _CHAR_FACTOR, 16), _VARCHAR_MAX)
        return f"VARCHAR({n})", None

    if base == "json":
        return ("STRING", None) if hive else ("JSON", None)

    # --- unknown ---
    return "STRING", f"{UNMAPPED_PREFIX}: {base or mysql_type} 无映射规则，回退 STRING"
