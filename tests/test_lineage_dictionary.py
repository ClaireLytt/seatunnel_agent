# -*- coding: utf-8 -*-
"""Tests for the data dictionary generator (data_lineage.dictionary).

Deterministic only — the optional LLM description pass is tested with a
stubbed client, never a real call.
"""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from seatunnel_agent.cli import cli
from seatunnel_agent.data_lineage.dictionary import (
    add_llm_descriptions,
    build_dictionary,
    render_dictionary_markdown,
)
from seatunnel_agent.data_lineage.loaders import build_graph

runner = CliRunner()

DEMO = Path(__file__).resolve().parents[1] / "examples" / "lineage_demo"


def _entries():
    graph, _ = build_graph(sql_dir=DEMO, use_cache=False)
    return build_dictionary(graph)


def test_dictionary_structure_from_demo():
    entries = _entries()
    by_table = {e["table"]: e for e in entries}
    assert len(entries) == 7
    gmv = by_table["dws.gmv_daily"]
    assert gmv["layer"] == "dws"
    assert "dwd.orders_di" in gmv["upstreams"]
    assert "ads.city_gmv_report" in gmv["downstreams"]
    assert "gmv" in gmv["columns"]
    assert "dwd.orders_di.amount" in gmv["columns"]["gmv"]["sources"]
    # aggregation flag propagated from the column edge
    assert gmv["columns"]["gmv"]["is_aggregation"]


def test_dictionary_sorted_by_layer():
    layers = [e["layer"] for e in _entries()]
    order = {"ods": 0, "dwd": 1, "dwm": 2, "dws": 3, "ads": 4, "rpt": 5}
    ranks = [order.get(la, 9) for la in layers]
    assert ranks == sorted(ranks)


def test_render_markdown_zh_and_en():
    entries = _entries()
    zh = render_dictionary_markdown(entries, "zh")
    assert zh.startswith("# 数据字典")
    assert "共 7 表" in zh
    assert "## dws.gmv_daily `dws`" in zh
    assert "`dwd.orders_di.amount`" in zh
    en = render_dictionary_markdown(entries, "en")
    assert en.startswith("# Data Dictionary")
    assert "7 tables" in en and "**Upstream**" in en


def test_llm_descriptions_are_additive(monkeypatch):
    entries = _entries()

    class FakeResp:
        reply_text = ("dws.gmv_daily: 渠道日 GMV 汇总表\n"
                      "not_a_table: ignored\n"
                      "garbage line without separator")

    class FakeClient:
        def __init__(self, settings): pass
        def chat(self, *a, **kw): return FakeResp()

    monkeypatch.setattr("seatunnel_agent.llm.LLMClient", FakeClient)
    filled = add_llm_descriptions(object(), entries, "zh")
    assert filled == 1
    gmv = next(e for e in entries if e["table"] == "dws.gmv_daily")
    assert gmv["description"] == "渠道日 GMV 汇总表"
    md = render_dictionary_markdown(entries, "zh")
    assert "llm-generated" in md
    # tables the LLM didn't name stay untouched
    assert all(not e["description"] for e in entries
               if e["table"] != "dws.gmv_daily")


def test_cli_datadict_to_file(tmp_path):
    out = tmp_path / "dict.md"
    res = runner.invoke(cli, [
        "datadict", "-d", str(DEMO), "-o", str(out),
    ])
    assert res.exit_code == 0, res.output
    text = out.read_text(encoding="utf-8")
    assert "# 数据字典" in text
    assert "ads.city_gmv_report" in text


def test_cli_datadict_stdout_en():
    res = runner.invoke(cli, ["datadict", "-d", str(DEMO), "--lang", "en"])
    assert res.exit_code == 0, res.output
    assert "# Data Dictionary" in res.output
