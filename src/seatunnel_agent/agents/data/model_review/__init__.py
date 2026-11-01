"""建模体检 — 数仓 DDL → 星型结构分级发现.

Deterministic core: parse the DDL (schema_drift parser reused),
classify tables by prefix (dim / dwd·dws facts / ods·stg raw), and
grade the star schema — keyless dimensions, unpartitioned or
dimension-less facts, descriptive attributes leaked into or copied
across facts, measure-less aggregates, over-wide tables.  Distinct from
metadata_quality (declaration conventions) and layer_check (lineage
layering).  No database connection.
"""

from .report import render_markdown
from .reviewer import ModelFinding, ModelReport, review_model

__all__ = [
    "ModelFinding",
    "ModelReport",
    "render_markdown",
    "review_model",
]
