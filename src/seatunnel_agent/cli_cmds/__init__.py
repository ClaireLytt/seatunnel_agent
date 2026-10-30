from __future__ import annotations

from . import (
    checks,
    core,
    lineage,
    perf_ops,
    pipeline_ops,
    platform,
    skew,
    sql_review,
    text2sql,
)


def register(cli) -> None:
    core.register(cli)
    sql_review.register(cli)
    lineage.register(cli)
    skew.register(cli)
    text2sql.register(cli)
    checks.register(cli)
    platform.register(cli)
    pipeline_ops.register(cli)
    perf_ops.register(cli)
