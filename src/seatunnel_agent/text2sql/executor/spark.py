"""Spark SQL executor via Spark Thrift Server (pyhive, same protocol as Hive)."""

from __future__ import annotations

from .hive import HiveExecutor


class SparkSqlExecutor(HiveExecutor):
    """Spark Thrift Server uses the same thrift protocol as HiveServer2.

    Default port is 10001 instead of 10000, but everything else
    (SHOW TABLES, DESCRIBE FORMATTED, SHOW PARTITIONS) works identically.
    """
    pass
