"""Tests for scripts/new_agent.py — the agent-factory scaffolder.

Runs against a throwaway fake repo in tmp_path, never the real tree.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "new_agent", ROOT / "scripts" / "new_agent.py")
new_agent = importlib.util.module_from_spec(_spec)
sys.modules["new_agent"] = new_agent
_spec.loader.exec_module(new_agent)

_CONFIG_BODY = "export default {}\n"


@pytest.fixture()
def fake_repo(tmp_path: Path) -> Path:
    donor = tmp_path / "frontend" / "donor_agent"
    (donor / "src").mkdir(parents=True)
    for cfg in new_agent._CONFIGS:
        (donor / cfg).write_text(_CONFIG_BODY, encoding="utf-8")
    (donor / "index.html").write_text(
        "<title>Donor Title</title>", encoding="utf-8")
    (donor / "package.json").write_text(
        '{\n  "name": "donor_agent"\n}\n', encoding="utf-8")
    (donor / "vite.config.ts").write_text(
        "base: '/donor/',\napiPath: '/api/donor',\n", encoding="utf-8")
    for rel in new_agent._SRC_COPY:
        (donor / "src" / rel).write_text(
            "const BASE = '/api/donor'\n// Donor Title /donor/ donor_agent\n",
            encoding="utf-8")
    (tmp_path / "frontend" / "package.json").write_text(
        '{\n  "workspaces": [\n    "shared",\n    "donor_agent",\n  ]\n}\n',
        encoding="utf-8")
    (tmp_path / "tests").mkdir()
    return tmp_path


def test_scaffold_frontend_ports_names(fake_repo: Path):
    created = new_agent.scaffold_frontend(
        fake_repo, "csv_doctor", "/csvdoctor", "CSV Doctor", "donor_agent")
    assert "frontend/csv_doctor/vite.config.ts" in [
        c.replace("\\", "/") for c in created]
    vite = (fake_repo / "frontend" / "csv_doctor" /
            "vite.config.ts").read_text(encoding="utf-8")
    assert "base: '/csvdoctor/'" in vite
    assert "apiPath: '/api/csvdoctor'" in vite
    html = (fake_repo / "frontend" / "csv_doctor" /
            "index.html").read_text(encoding="utf-8")
    assert "<title>CSV Doctor</title>" in html
    pkg = (fake_repo / "frontend" / "csv_doctor" /
           "package.json").read_text(encoding="utf-8")
    assert '"csv_doctor"' in pkg
    api = (fake_repo / "frontend" / "csv_doctor" / "src" /
           "api.ts").read_text(encoding="utf-8")
    assert "/api/csvdoctor" in api and "donor" not in api.split("//")[0]


def test_register_workspace_after_donor(fake_repo: Path):
    new_agent.register_workspace(fake_repo, "csv_doctor", "donor_agent")
    doc = json.loads((fake_repo / "frontend" / "package.json")
                     .read_text(encoding="utf-8").replace(",\n  ]", "\n  ]"))
    ws = doc["workspaces"]
    assert ws.index("csv_doctor") == ws.index("donor_agent") + 1


def test_page_test_spec_has_factory_and_todos(fake_repo: Path):
    rel = new_agent.write_page_test(fake_repo, "csv_doctor", "/csvdoctor",
                                    "CSV Doctor")
    body = (fake_repo / rel).read_text(encoding="utf-8")
    assert "standard_page_tests" in body
    assert "CSVDOCTOR_API_ALLOWED_DIRS" in body
    assert "agents.data.csv_doctor.manifest" in body
    assert body.count("<TODO") == 4


def test_collisions_refused(fake_repo: Path):
    new_agent.scaffold_frontend(fake_repo, "csv_doctor", "/csvdoctor",
                                "CSV Doctor", "donor_agent")
    with pytest.raises(SystemExit, match="already exists"):
        new_agent.scaffold_frontend(fake_repo, "csv_doctor", "/csvdoctor",
                                    "CSV Doctor", "donor_agent")
    with pytest.raises(SystemExit, match="not found"):
        new_agent.scaffold_frontend(fake_repo, "other", "/other", "T",
                                    "nope_agent")
