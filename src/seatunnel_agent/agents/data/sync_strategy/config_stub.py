"""SeaTunnel job-config skeletons for each recommended strategy.

Deterministic string templates: the strategy decides the source block
(plain Jdbc query, watermark/PK-bounded query, or MySQL-CDC) and the
job mode; connection details and the sink stay as placeholders for the
user to fill in.  The inventory's optional ``update_ts_col`` /
``pk_col`` name the real columns when known.
"""

from __future__ import annotations

from .advisor import SourceTable

__all__ = ["config_stub"]

_SINK = ('sink {\n  # fill in: the warehouse sink '
         '(Hive / Doris / Jdbc ...)\n}')


def _parallelism(rows: int) -> int:
    """Scale source parallelism with table size (unknown rows → 2)."""
    if not rows:
        return 2
    if rows < 1_000_000:
        return 1
    if rows < 100_000_000:
        return 2
    return 4


def _env(table: SourceTable, mode: str) -> str:
    return (f"env {{\n  parallelism = {_parallelism(table.rows)}\n"
            f'  job.mode = "{mode}"\n}}')


def _jdbc_source(query: str, note: str = "") -> str:
    lines = ["source {", "  Jdbc {",
             '    url = "jdbc:mysql://<host>:3306/<db>"',
             '    driver = "com.mysql.cj.jdbc.Driver"',
             '    user = "<user>"',
             '    password = "<password>"']
    if note:
        lines.append(f"    # {note}")
    lines.append(f'    query = "{query}"')
    lines.extend(["  }", "}"])
    return "\n".join(lines)


def config_stub(table: SourceTable, strategy: str) -> str:
    ts_col = table.update_ts_col or "<update_ts_col>"
    pk_col = table.pk_col or "<pk_col>"
    if strategy == "cdc":
        db, _, name = table.table.rpartition(".")
        source = "\n".join([
            "source {",
            "  MySQL-CDC {",
            '    base-url = "jdbc:mysql://<host>:3306/<db>"',
            '    username = "<user>"',
            '    password = "<password>"',
            f'    table-names = ["{db or "<db>"}.{name}"]',
            '    startup.mode = "initial"',
            "  }",
            "}"])
        return "\n\n".join([_env(table, "STREAMING"), source, _SINK])
    if strategy == "incr_timestamp":
        source = _jdbc_source(
            f"SELECT * FROM {table.table} "
            f"WHERE {ts_col} >= '${{watermark}}'",
            note="keep an overlap window below the stored watermark "
                 "to catch late updates")
    elif strategy == "incr_pk":
        source = _jdbc_source(
            f"SELECT * FROM {table.table} "
            f"WHERE {pk_col} > ${{last_max_pk}}",
            note="append-only pull; schedule periodic full compares")
    else:  # full
        source = _jdbc_source(f"SELECT * FROM {table.table}")
    return "\n\n".join([_env(table, "BATCH"), source, _SINK])
