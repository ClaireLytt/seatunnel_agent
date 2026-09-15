"""Apache Doris / StarRocks executor — MySQL protocol compatible."""

from __future__ import annotations

from .mysql import MySQLExecutor


class DorisExecutor(MySQLExecutor):
    """Doris uses the MySQL protocol (default port 9030), so we reuse MySQLExecutor."""
    pass
