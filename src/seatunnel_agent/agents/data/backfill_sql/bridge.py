"""Bridge from the backfill planner's plan JSON to spec skeletons.

The planner (``/backfill``) answers *which* tables and dates need a
backfill; this agent answers *how*.  ``specs_from_plan`` takes the
planner's ``plan_to_dict`` JSON and emits one ready-to-edit spec per
impacted table — the exact missing/cascade dates carried over as the
explicit ``dates`` list, the source SELECT left as a bounded template
to fill in.
"""

from __future__ import annotations

import json
from typing import Any

__all__ = ["specs_from_plan"]


def specs_from_plan(plan_json: str, partition_col: str = "dt",
                    dialect: str = "hive") -> list[dict[str, Any]]:
    stripped = (plan_json or "").strip()
    if not stripped:
        raise ValueError("empty plan")
    data = json.loads(stripped)
    if isinstance(data, dict) and "result" in data:  # raw API response
        data = data["result"]
    if not isinstance(data, dict) or not isinstance(data.get("tables"), list):
        raise ValueError("plan JSON needs a 'tables' list "
                         "(backfill planner plan_to_dict output)")
    specs: list[dict[str, Any]] = []
    for entry in data["tables"]:
        table = str(entry.get("table") or "").strip()
        dates = sorted(set((entry.get("missing") or [])
                           + (entry.get("cascade") or [])
                           + (entry.get("dates") or [])))
        if not table or not dates:
            continue
        specs.append({
            "table": table,
            "partition_col": partition_col,
            "dates": dates,
            "mode": "overwrite",
            "dialect": dialect,
            "source": (f"SELECT /* fill in the columns */ * "
                       f"FROM <upstream_of_{table.rsplit('.', 1)[-1]}> "
                       f"WHERE {partition_col} = '{{date}}'"),
        })
    if not specs:
        raise ValueError("plan contains no tables with dates to backfill")
    return specs
