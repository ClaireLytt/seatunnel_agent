"""Database executor package — multi-engine support for Text2SQL."""

from .base import (
    DS_DEFAULTS,
    DS_TYPES,
    DIALECT_NAMES,
    PARTITION_ENGINES,
    DatabaseConfig,
    DatabaseExecutor,
    QueryResult,
    config_from_env,
    create_executor,
    schema_ddl_path_from_env,
)
from .hive import HiveExecutor, hive_config_from_env

HiveConfig = DatabaseConfig

__all__ = [
    "DatabaseConfig",
    "DatabaseExecutor",
    "QueryResult",
    "DS_DEFAULTS",
    "DS_TYPES",
    "DIALECT_NAMES",
    "PARTITION_ENGINES",
    "config_from_env",
    "create_executor",
    "schema_ddl_path_from_env",
    "HiveConfig",
    "HiveExecutor",
    "hive_config_from_env",
]
