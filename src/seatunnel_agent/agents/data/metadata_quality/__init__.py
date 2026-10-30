"""Metadata quality — DDL-level conventions check.

sql_review judges how queries are written, schema_drift judges how
structures change; this agent judges how tables are *declared*:

* **comment coverage** — columns without a COMMENT, per-table percentage;
* **layer naming** — table prefix vs database layer (ods_/dwd_/dws_/ads_/dim_);
* **type anti-patterns** — money-named columns on FLOAT/DOUBLE (precision
  loss; use DECIMAL), date-named non-partition columns on bare STRING.

Fully deterministic — DDL text in, severity-graded report out.
"""

from .checker import MetaQualityReport, check_dir, check_sql_text
from .report import render_markdown

__all__ = [
    "MetaQualityReport",
    "check_dir",
    "check_sql_text",
    "render_markdown",
]
