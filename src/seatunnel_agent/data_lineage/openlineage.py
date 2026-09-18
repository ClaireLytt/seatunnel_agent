# -*- coding: utf-8 -*-
"""Export the lineage graph as an OpenLineage RunEvent.

Pure functions, no network I/O — the produced dict follows the OpenLineage
1.x RunEvent spec so it can be POSTed to any OpenLineage-compatible backend
(Marquez, DataHub, Atlan…) or archived as JSON.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .graph import ColumnEdge, LineageGraph

PRODUCER = "https://github.com/ClaireLytt/seatunnel_agent"
_RUN_EVENT_SCHEMA = (
    "https://openlineage.io/spec/1-0-5/OpenLineage.json#/definitions/RunEvent"
)
_COLUMN_LINEAGE_SCHEMA = (
    "https://openlineage.io/spec/facets/1-2-0/ColumnLineageDatasetFacet.json"
)


def _column_lineage_facet(
    edges_by_column: dict[str, list[ColumnEdge]], namespace: str
) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for dst_column in sorted(edges_by_column):
        edges = edges_by_column[dst_column]
        fields[dst_column] = {
            "inputFields": [
                {
                    "namespace": namespace,
                    "name": e.src_table,
                    "field": e.src_column,
                }
                for e in edges
            ],
            "transformationDescription": next(
                (e.expression for e in edges if e.expression), ""
            ),
            "transformationType": (
                "AGGREGATION" if any(e.is_aggregation for e in edges)
                else "IDENTITY"
            ),
        }
    return {
        "_producer": PRODUCER,
        "_schemaURL": _COLUMN_LINEAGE_SCHEMA,
        "fields": fields,
    }


def _provenance_facet(
    graph: LineageGraph, dst_table: str
) -> dict[str, Any]:
    upstream = []
    for up in sorted(graph.upstream.get(dst_table, set())):
        meta = graph.edge_meta.get((up, dst_table))
        entry: dict[str, Any] = {"table": up}
        if meta is not None:
            entry["sources"] = sorted(meta.sources)
            entry["confidence"] = meta.confidence
        upstream.append(entry)
    return {"_producer": PRODUCER, "upstream": upstream}


def to_openlineage(
    graph: LineageGraph,
    namespace: str = "default",
    job_name: str = "seatunnel_lineage",
    run_id: str | None = None,
    event_time: str | None = None,
) -> dict[str, Any]:
    """The whole graph as one OpenLineage RunEvent dict.

    Tables with downstream edges become ``inputs``, tables with upstream
    edges become ``outputs`` (a mid-chain table appears in both). Column
    lineage and edge provenance ride on the output datasets as facets.
    """
    input_names = sorted(k for k, v in graph.downstream.items() if v)
    output_names = sorted(k for k, v in graph.upstream.items() if v)

    columns_by_table: dict[str, dict[str, list[ColumnEdge]]] = {}
    for (dst_table, dst_column), edges in graph.column_up.items():
        columns_by_table.setdefault(dst_table, {}).setdefault(
            dst_column, []
        ).extend(edges)

    inputs = [
        {"namespace": namespace, "name": name, "facets": {}}
        for name in input_names
    ]
    outputs = []
    for name in output_names:
        facets: dict[str, Any] = {
            "seatunnelAgentLineage": _provenance_facet(graph, name),
        }
        if name in columns_by_table:
            facets["columnLineage"] = _column_lineage_facet(
                columns_by_table[name], namespace
            )
        outputs.append({"namespace": namespace, "name": name, "facets": facets})

    return {
        "eventType": "COMPLETE",
        "eventTime": event_time
        or datetime.now(timezone.utc).isoformat(),
        "producer": PRODUCER,
        "schemaURL": _RUN_EVENT_SCHEMA,
        "run": {"runId": run_id or str(uuid.uuid4()), "facets": {}},
        "job": {"namespace": namespace, "name": job_name, "facets": {}},
        "inputs": inputs,
        "outputs": outputs,
    }


def export_openlineage_file(
    graph: LineageGraph,
    path: str | Path,
    namespace: str = "default",
    job_name: str = "seatunnel_lineage",
) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    event = to_openlineage(graph, namespace=namespace, job_name=job_name)
    out.write_text(
        json.dumps(event, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out
