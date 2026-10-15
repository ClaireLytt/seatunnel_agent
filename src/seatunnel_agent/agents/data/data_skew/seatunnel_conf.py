"""SeaTunnel config (HOCON) parsing/rewriting for split-key analysis.

Moved verbatim out of splitkey.py, which re-exports the public names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .measure import (
    MAX_CANDIDATES,
    SplitKeyError,
)

_IDENT = r"[A-Za-z_][\w$]*"

_TABLE_RE = re.compile(rf"^{_IDENT}(\.{_IDENT})?$")

_QUERY_FROM_RE = re.compile(
    rf"\bfrom\s+({_IDENT}(?:\.{_IDENT})?)\s*(?:$|;|\bwhere\b|\blimit\b)",
    re.IGNORECASE,
)

_OPT_VALUE = r"(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|[^\s,}]+)"

_APPLY_ANCHOR_RE = re.compile(
    r"(?<![\w$.-])(?:table_path|table_name|table-names|table-name"
    r"|table|query)" + _OPT_VALUE)

_APPLY_PN_RE = re.compile(r"(?<![\w$.-])partition_num" + _OPT_VALUE)

_SINK_KEY_OPTIONS = ("sharding_key", "partition_by", "primary_keys")

@dataclass
class SourceSpec:
    """The parsed JDBC-ish source block of a SeaTunnel job config."""
    plugin: str = ""
    table: str = ""
    partition_column: str = ""
    partition_num: int = 0
    parallelism: int = 0
    # which config option carried the split key — "partition_column" (JDBC)
    # or the CDC chunk key; apply_split_key() writes back through it
    split_option: str = "partition_column"

    @property
    def tasks(self) -> int:
        """Effective parallel read tasks the split key must feed."""
        return max(self.partition_num, self.parallelism, 2)


def _spec_from_params(plugin: str, params, parallelism: int) -> SourceSpec | None:
    """One source entry → SourceSpec, or None when no base table resolves."""

    def _get(key: str, default: str = "") -> str:
        v = params.get(key, default)
        if isinstance(v, (list, tuple)):  # CDC list options: first entry
            v = v[0] if v else default
        return str(v).strip() if v is not None else default

    def _get_any(*keys: str) -> str:
        for key in keys:
            v = _get(key)
            if v:
                return v
        return ""

    # JDBC snake_case options first, then the CDC connectors' hyphenated
    # ones (MySQL-CDC & co.; table-names entries are usually db-qualified)
    table = _get_any("table_path", "table_name", "table",
                     "table-name", "table-names")
    if not table:
        query = _get("query")
        m = _QUERY_FROM_RE.search(query) if query else None
        if m:
            table = m.group(1)
    if table and "." not in table:
        # CDC splits database and table into separate options
        db = _get_any("database-name", "database-names", "database_name")
        if db:
            table = f"{db}.{table}"
    if not table or not _TABLE_RE.match(table):
        return None

    def _int(key: str) -> int:
        try:
            return int(str(params.get(key, 0) or 0))
        except (TypeError, ValueError):
            return 0

    # CDC jobs split the snapshot by chunk key-column, not
    # partition_column — both are "the column parallel reads split on"
    split_option = "partition_column"
    partition_column = _get("partition_column")
    if not partition_column:
        cdc_key = _get("scan.incremental.snapshot.chunk.key-column")
        if cdc_key:
            partition_column, split_option = (
                cdc_key, "scan.incremental.snapshot.chunk.key-column")

    return SourceSpec(
        plugin=plugin,
        table=table,
        partition_column=partition_column,
        partition_num=_int("partition_num"),
        parallelism=parallelism,
        split_option=split_option,
    )


def parse_seatunnel_sources(conf_text: str) -> list[SourceSpec]:
    """Every resolvable source's base table + split settings, config order.

    Accepts both source shapes: ``source { Jdbc { … } }`` and the list form
    ``source = [{ plugin_name = "Jdbc", … }]``.  Understands the JDBC
    options (``table_path`` / ``table_name`` / ``partition_column``) and the
    CDC connectors' hyphenated ones (``database-name(s)`` /
    ``table-name(s)``, list options take the first entry, and the
    incremental-snapshot split key
    ``scan.incremental.snapshot.chunk.key-column``).

    Source entries whose base table cannot be resolved (e.g. a joining
    query) are skipped; raises ``spk_no_source`` when no source block
    exists and ``spk_no_table`` when none of them resolves.
    """
    try:
        from pyhocon import ConfigFactory
    except ImportError as exc:  # pragma: no cover — dependency of the app
        raise SplitKeyError("spk_parse_fail", f"pyhocon not installed: {exc}")
    try:
        conf = ConfigFactory.parse_string(conf_text)
    except Exception as exc:
        raise SplitKeyError("spk_parse_fail", str(exc))

    source = conf.get("source", None)
    entries: list[tuple[str, object]] = []
    if isinstance(source, list):
        for item in source:
            if hasattr(item, "get"):
                entries.append((str(item.get("plugin_name", "") or "Jdbc"), item))
    elif source is not None and hasattr(source, "items"):
        for name, block in source.items():
            if hasattr(block, "get"):
                entries.append((str(name), block))
    if not entries:
        raise SplitKeyError("spk_no_source")

    env = conf.get("env", None)
    parallelism = 0
    if env is not None and hasattr(env, "get"):
        try:
            parallelism = int(str(env.get("parallelism", 0) or 0))
        except (TypeError, ValueError):
            parallelism = 0

    specs = []
    for plugin, params in entries:
        spec = _spec_from_params(plugin, params, parallelism)
        if spec is not None:
            specs.append(spec)
    if not specs:
        raise SplitKeyError("spk_no_table")
    return specs


def parse_seatunnel_source(conf_text: str) -> SourceSpec:
    """First resolvable source — the single-source compatibility path."""
    return parse_seatunnel_sources(conf_text)[0]


def _is_code_line(line: str) -> bool:
    ls = line.lstrip()
    return not (ls.startswith("#") or ls.startswith("//"))


def apply_split_key(conf_text: str, spec: SourceSpec, column: str,
                    partition_num: int = 0) -> str:
    """Return *conf_text* with its split key rewritten to *column*.

    Text-level edit so the config keeps its comments and formatting
    (comment lines are never touched): replaces the value of the option
    that carried the key (``spec.split_option``); when no split key was
    configured, appends ``partition_column`` (+ ``partition_num``) inline
    after the table option. Raises SplitKeyError('spk_apply_fail') when no
    anchor is found."""
    opt = spec.split_option or "partition_column"
    opt_re = re.compile(rf"(?<![\w$.-]){re.escape(opt)}{_OPT_VALUE}")
    lines = conf_text.split("\n")

    # partition_num travels with the JDBC option only (a CDC chunk key
    # has no partition_num); update an existing one in place first
    need_pn = bool(partition_num) and opt == "partition_column"
    if need_pn:
        for i, line in enumerate(lines):
            if not _is_code_line(line):
                continue
            m = _APPLY_PN_RE.search(line)
            if m:
                lines[i] = (line[:m.start()]
                            + f"partition_num{m.group(1)}{partition_num}"
                            + line[m.end():])
                need_pn = False
                break

    for i, line in enumerate(lines):
        if not _is_code_line(line):
            continue
        m = opt_re.search(line)
        if not m:
            continue
        new = f'{opt}{m.group(1)}"{column}"'
        if need_pn:
            new += f", partition_num = {partition_num}"
        lines[i] = line[:m.start()] + new + line[m.end():]
        return "\n".join(lines)

    if opt != "partition_column":
        # a CDC chunk key written in nested (non-dotted) HOCON — no
        # reliable text anchor, refuse rather than guess
        raise SplitKeyError("spk_apply_fail")
    for i, line in enumerate(lines):
        if not _is_code_line(line):
            continue
        m = _APPLY_ANCHOR_RE.search(line)
        if not m:
            continue
        insert = f', partition_column = "{column}"'
        if need_pn:
            insert += f", partition_num = {partition_num}"
        lines[i] = line[:m.end()] + insert + line[m.end():]
        return "\n".join(lines)
    raise SplitKeyError("spk_apply_fail")


@dataclass
class SinkSpec:
    """One sink option that distributes rows by column(s)."""
    plugin: str
    option: str            # which config option carried the key(s)
    columns: list[str]
    table: str = ""        # sink table label, best-effort (for the report)


def parse_seatunnel_sinks(conf_text: str) -> list[SinkSpec]:
    """Every sink option that names distribution columns, config order.

    Understands the ClickHouse ``sharding_key``, the file sinks'
    ``partition_by`` and the JDBC sinks' ``primary_keys`` (upsert key).
    Sinks without any of them (e.g. Doris, whose bucket key lives in the
    Doris DDL) yield nothing. Never raises on a config that
    :func:`parse_seatunnel_sources` accepted; [] when there is no sink."""
    try:
        from pyhocon import ConfigFactory
        conf = ConfigFactory.parse_string(conf_text)
    except Exception:
        return []

    sink = conf.get("sink", None)
    entries: list[tuple[str, object]] = []
    if isinstance(sink, list):
        for item in sink:
            if hasattr(item, "get"):
                entries.append((str(item.get("plugin_name", "") or "Sink"), item))
    elif sink is not None and hasattr(sink, "items"):
        for name, block in sink.items():
            if hasattr(block, "get"):
                entries.append((str(name), block))

    out: list[SinkSpec] = []
    for plugin, params in entries:
        table = ""
        for key in ("table.identifier", "table", "table_name", "database"):
            try:
                v = params.get(key, None)
            except Exception:
                v = None
            if v is not None and not hasattr(v, "items"):
                table = str(v).strip()
                if table:
                    break
        for opt in _SINK_KEY_OPTIONS:
            v = params.get(opt, None)
            if v is None:
                continue
            cols = [str(x).strip() for x in v] if isinstance(v, (list, tuple)) \
                else [s.strip() for s in str(v).split(",")]
            cols = [c for c in cols if c and _TABLE_RE.match(c)]
            if cols:
                out.append(SinkSpec(plugin=plugin, option=opt,
                                    columns=cols[:MAX_CANDIDATES], table=table))
    return out
