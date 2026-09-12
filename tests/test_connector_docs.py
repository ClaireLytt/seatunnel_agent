"""Tests for connector documentation query tool."""

from __future__ import annotations

import json
import tempfile as _tempfile
from pathlib import Path

from seatunnel_agent.config import Settings
from seatunnel_agent.connector_docs import (
    CONNECTOR_DOCS,
    list_documented_connectors,
    query_connector,
)
from seatunnel_agent.tools import execute_tool

_tmp = _tempfile.gettempdir()

FAKE_SETTINGS = Settings(
    api_key="sk-test",
    seatunnel_home=str(Path(_tmp) / "nonexistent-seatunnel"),
    seatunnel_bin=str(Path(_tmp) / "nonexistent-seatunnel" / "bin" / "seatunnel.sh"),
)


class TestQueryConnector:
    def test_query_full_connector(self):
        result = query_connector("FakeSource")
        assert result["connector_name"] == "FakeSource"
        assert result["connector_type"] == "source"
        assert "description" in result
        assert isinstance(result["optional_params"], list)

    def test_query_jdbc_has_required_params(self):
        result = query_connector("Jdbc")
        assert result["connector_name"] == "Jdbc"
        assert result["connector_type"] == "both"
        req_names = [p["name"] for p in result["required_params"]]
        assert "url" in req_names
        assert "driver" in req_names

    def test_query_specific_param(self):
        result = query_connector("Jdbc", "url")
        assert "param_detail" in result
        detail = result["param_detail"]
        assert detail["name"] == "url"
        assert detail["type"] == "string"
        assert detail["required"] is True

    def test_query_unknown_connector(self):
        result = query_connector("NoSuchConnector")
        assert "error" in result
        assert "available_connectors" in result
        assert len(result["available_connectors"]) >= 11

    def test_query_unknown_param(self):
        result = query_connector("Jdbc", "nonexistent_param")
        assert "error" in result
        assert "available_params" in result
        assert "url" in result["available_params"]

    def test_case_insensitive_lookup(self):
        result = query_connector("fakesource")
        assert result["connector_name"] == "FakeSource"

    def test_connector_doc_types(self):
        for name, doc in CONNECTOR_DOCS.items():
            assert doc.connector_type in ("source", "sink", "both"), (
                f"{name} has invalid type: {doc.connector_type}"
            )


class TestListDocumentedConnectors:
    def test_at_least_11_connectors(self):
        connectors = list_documented_connectors()
        assert len(connectors) >= 11

    def test_sorted(self):
        connectors = list_documented_connectors()
        assert connectors == sorted(connectors)

    def test_includes_common_connectors(self):
        connectors = list_documented_connectors()
        for expected in ["FakeSource", "Console", "Jdbc", "Kafka"]:
            assert expected in connectors


class TestExecuteToolIntegration:
    def test_query_connector_docs_via_execute(self):
        result = json.loads(execute_tool(
            "query_connector_docs",
            {"connector_name": "Kafka"},
            FAKE_SETTINGS,
        ))
        assert result["connector_name"] == "Kafka"
        assert "required_params" in result

    def test_query_connector_docs_with_param(self):
        result = json.loads(execute_tool(
            "query_connector_docs",
            {"connector_name": "Kafka", "param_name": "topic"},
            FAKE_SETTINGS,
        ))
        assert "param_detail" in result
        assert result["param_detail"]["name"] == "topic"

    def test_query_connector_docs_unknown(self):
        result = json.loads(execute_tool(
            "query_connector_docs",
            {"connector_name": "Unknown"},
            FAKE_SETTINGS,
        ))
        assert "error" in result
