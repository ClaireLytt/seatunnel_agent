"""SeaTunnel sync-config generation + JDBC URL/driver helpers (C)."""

from __future__ import annotations

from .models import ColumnMapping
from .sqlbase import quote_identifier

# ---------------------------------------------------------------------------
# JDBC helpers  (C)
# ---------------------------------------------------------------------------

_JDBC_URL_PATTERNS: dict[str, str] = {
    "mysql":      "jdbc:mysql://{host}:{port}/{database}",
    "postgresql": "jdbc:postgresql://{host}:{port}/{database}",
    "sqlserver":  "jdbc:sqlserver://{host}:{port};databaseName={database}",
    "clickhouse": "jdbc:clickhouse://{host}:{port}/{database}",
    "doris":      "jdbc:mysql://{host}:{port}/{database}",
    "hive":       "jdbc:hive2://{host}:{port}/{database}",
    "sparksql":   "jdbc:hive2://{host}:{port}/{database}",
}

_JDBC_DRIVERS: dict[str, str] = {
    "mysql":      "com.mysql.cj.jdbc.Driver",
    "doris":      "com.mysql.cj.jdbc.Driver",
    "postgresql": "org.postgresql.Driver",
    "sqlserver":  "com.microsoft.sqlserver.jdbc.SQLServerDriver",
    "clickhouse": "com.clickhouse.jdbc.ClickHouseDriver",
    "hive":       "org.apache.hive.jdbc.HiveDriver",
    "sparksql":   "org.apache.hive.jdbc.HiveDriver",
}


def build_jdbc_url(ds_type: str, host: str, port: int, database: str) -> str:
    pattern = _JDBC_URL_PATTERNS.get(ds_type, "jdbc:{ds}://{host}:{port}/{database}")
    return pattern.format(ds=ds_type, host=host, port=port, database=database)


def get_jdbc_driver(ds_type: str) -> str:
    return _JDBC_DRIVERS.get(ds_type, "")


def _escape_hocon(s: str) -> str:
    """Escape a string value for embedding in a HOCON double-quoted string."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("$", "$$")


def generate_sync_config(
    ds_type_a: str, host_a: str, port_a: int, db_a: str,
    user_a: str | None, pwd_a: str | None, table_a: str,
    ds_type_b: str, host_b: str, port_b: int, db_b: str,
    user_b: str | None, pwd_b: str | None, table_b: str,
    column_mapping: ColumnMapping | None = None,
    parallelism: int = 2,
) -> str:
    """Generate a SeaTunnel HOCON sync job config: source A -> sink B."""
    url_a = build_jdbc_url(ds_type_a, host_a, port_a, db_a)
    url_b = build_jdbc_url(ds_type_b, host_b, port_b, db_b)
    drv_a = get_jdbc_driver(ds_type_a)
    drv_b = get_jdbc_driver(ds_type_b)

    transform_block = "transform {\n}"
    if column_mapping:
        # SeaTunnel's SQL transform runs in its own engine, which quotes
        # identifiers with backticks regardless of source/sink dialect.
        field_list = ", ".join(
            f"{quote_identifier(v, 'mysql')} AS {quote_identifier(k, 'mysql')}"
            for k, v in column_mapping.items()
        )
        transform_block = (
            'transform {\n'
            '  Sql {\n'
            f'    query = "{_escape_hocon(f"SELECT *, {field_list} FROM source_table")}"\n'
            '  }\n'
            '}'
        )

    lines = [
        'env {',
        '  job.mode = "BATCH"',
        f'  parallelism = {int(parallelism)}',
        '}',
        '',
        'source {',
        '  Jdbc {',
        f'    url = "{_escape_hocon(url_a)}"',
        f'    driver = "{drv_a}"',
    ]
    if user_a:
        lines.append(f'    user = "{_escape_hocon(user_a)}"')
    if pwd_a:
        lines.append(f'    password = "{_escape_hocon(pwd_a)}"')
    lines += [
        f'    query = "{_escape_hocon(f"SELECT * FROM {quote_identifier(table_a, ds_type_a)}")}"',
        '  }',
        '}',
        '',
        transform_block,
        '',
        'sink {',
        '  Jdbc {',
        f'    url = "{_escape_hocon(url_b)}"',
        f'    driver = "{drv_b}"',
    ]
    if user_b:
        lines.append(f'    user = "{_escape_hocon(user_b)}"')
    if pwd_b:
        lines.append(f'    password = "{_escape_hocon(pwd_b)}"')
    lines += [
        f'    database = "{_escape_hocon(db_b)}"',
        f'    table = "{_escape_hocon(table_b)}"',
        '    generate_sink_sql = true',
        '  }',
        '}',
    ]
    return "\n".join(lines)


