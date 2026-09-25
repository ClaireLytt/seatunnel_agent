# -*- coding: utf-8 -*-
"""OpenLineage export (data_lineage/openlineage.py)."""

from __future__ import annotations

import json

from seatunnel_agent.data_lineage.graph import ColumnEdge, LineageGraph
from seatunnel_agent.data_lineage.openlineage import (
    PRODUCER,
    export_openlineage_file,
    to_openlineage,
)


def _sample_graph() -> LineageGraph:
    g = LineageGraph()
    g.add_edge("zz.ods_orders", "zz.dwd_orders", source="sql", confidence="high")
    g.add_edge("zz.dwd_orders", "zz.dws_gmv", source="seatunnel", confidence="medium")
    g.add_column_edge(ColumnEdge(
        "zz.ods_orders", "amount", "zz.dwd_orders", "amount",
        expression="amount", is_aggregation=False,
    ))
    g.add_column_edge(ColumnEdge(
        "zz.dwd_orders", "amount", "zz.dws_gmv", "gmv",
        expression="SUM(amount)", is_aggregation=True,
    ))
    return g


def test_empty_graph_produces_valid_skeleton():
    event = to_openlineage(LineageGraph(), run_id="rid", event_time="2026-01-01T00:00:00+00:00")
    assert event["eventType"] == "COMPLETE"
    assert event["eventTime"] == "2026-01-01T00:00:00+00:00"
    assert event["producer"] == PRODUCER
    assert "RunEvent" in event["schemaURL"]
    assert event["run"]["runId"] == "rid"
    assert event["job"] == {"namespace": "default", "name": "seatunnel_lineage", "facets": {}}
    assert event["inputs"] == [] and event["outputs"] == []


def test_inputs_outputs_partition():
    event = to_openlineage(_sample_graph(), namespace="hive")
    input_names = [d["name"] for d in event["inputs"]]
    output_names = [d["name"] for d in event["outputs"]]
    assert input_names == ["zz.dwd_orders", "zz.ods_orders"]
    assert output_names == ["zz.dwd_orders", "zz.dws_gmv"]
    assert all(d["namespace"] == "hive" for d in event["inputs"] + event["outputs"])


def test_column_lineage_facet_content():
    event = to_openlineage(_sample_graph())
    dwd = next(d for d in event["outputs"] if d["name"] == "zz.dwd_orders")
    facet = dwd["facets"]["columnLineage"]
    assert "ColumnLineageDatasetFacet" in facet["_schemaURL"]
    amount = facet["fields"]["amount"]
    assert amount["inputFields"] == [
        {"namespace": "default", "name": "zz.ods_orders", "field": "amount"}
    ]
    assert amount["transformationType"] == "IDENTITY"
    assert amount["transformationDescription"] == "amount"


def test_aggregation_transformation_type():
    event = to_openlineage(_sample_graph())
    dws = next(d for d in event["outputs"] if d["name"] == "zz.dws_gmv")
    gmv = dws["facets"]["columnLineage"]["fields"]["gmv"]
    assert gmv["transformationType"] == "AGGREGATION"
    assert gmv["transformationDescription"] == "SUM(amount)"


def test_provenance_facet_has_sources_and_confidence():
    event = to_openlineage(_sample_graph())
    dws = next(d for d in event["outputs"] if d["name"] == "zz.dws_gmv")
    facet = dws["facets"]["seatunnelAgentLineage"]
    assert facet["upstream"] == [
        {"table": "zz.dwd_orders", "sources": ["seatunnel"], "confidence": "medium"}
    ]


def test_output_without_column_edges_has_no_column_facet():
    g = LineageGraph()
    g.add_edge("a.src", "a.dst")
    event = to_openlineage(g)
    dst = next(d for d in event["outputs"] if d["name"] == "a.dst")
    assert "columnLineage" not in dst["facets"]
    assert "seatunnelAgentLineage" in dst["facets"]


def test_export_file_roundtrip(tmp_path):
    out = export_openlineage_file(_sample_graph(), tmp_path / "sub" / "event.json")
    assert out.is_file()
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["eventType"] == "COMPLETE"
    assert len(doc["outputs"]) == 2
    assert doc["run"]["runId"]
