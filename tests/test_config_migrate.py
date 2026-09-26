# -*- coding: utf-8 -*-
"""Tests for the DataX/Sqoop → SeaTunnel migration agent (config_migrate).

Deterministic only — no LLM, no database, no network. Every generated
config must parse as HOCON with source+sink (the same check
`seatunnel-agent validate` performs).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from seatunnel_agent.cli import cli
from seatunnel_agent.config_migrate import (
    migrate_datax,
    migrate_dir,
    migrate_file,
    migrate_sqoop,
    migrate_text,
    render_batch_markdown,
    render_migrate_markdown,
)

runner = CliRunner()

DEMO = Path(__file__).resolve().parents[1] / "examples" / "migrate_demo"


def _hocon_ok(conf: str) -> None:
    pytest.importorskip("pyhocon")
    from pyhocon import ConfigFactory
    parsed = ConfigFactory.parse_string(conf)
    assert "source" in parsed and "sink" in parsed and "env" in parsed


# ─────────────────────────── DataX ───────────────────────────

def test_datax_mysql_to_doris_full_mapping():
    r = migrate_file(DEMO / "01_mysql_to_doris.json")
    assert r.ok and r.source_kind == "datax"
    assert r.reader == "mysqlreader" and r.writer == "doriswriter"
    conf = r.output_conf
    _hocon_ok(conf)
    assert 'url = "jdbc:mysql://10.0.0.1:3306/trade"' in conf
    assert "com.mysql.cj.jdbc.Driver" in conf
    assert ("select order_id, user_id, amount, dt from orders "
            "where dt = '${bizdate}'") in conf
    assert 'partition_column = "order_id"' in conf
    assert "parallelism = 4" in conf            # speed.channel
    assert 'fenodes = "10.0.0.9:8030"' in conf
    assert 'table.identifier = "dwd.orders_di"' in conf
    kinds = {i.kind for i in r.issues}
    assert {"split_pk", "error_limit"} <= kinds  # info-level notes


def test_datax_stream_to_mysql_warns():
    r = migrate_file(DEMO / "02_stream_to_mysql.json")
    assert r.ok                                  # warns are not failures
    conf = r.output_conf
    _hocon_ok(conf)
    assert "FakeSource" in conf
    assert "generate_sink_sql = true" in conf
    assert 'database = "test"' in conf           # parsed from jdbcUrl
    kinds = {i.kind for i in r.issues}
    assert {"write_mode", "pre_post_sql", "stream_reader"} <= kinds


def test_datax_unknown_plugin_is_error_with_todo():
    r = migrate_file(DEMO / "03_unknown_plugin.json")
    assert not r.ok
    assert any(i.kind == "unknown_reader" and i.level == "error"
               for i in r.issues)
    assert "# unsupported DataX reader: mongodbreader" in r.output_conf
    _hocon_ok(r.output_conf)                     # TODO block still valid HOCON


def test_datax_bad_json_and_not_datax():
    assert migrate_datax("{ not json").issues[0].kind == "bad_json"
    r = migrate_datax(json.dumps({"job": {"content": [{}]}}))
    assert not r.ok and r.issues[-1].kind == "not_datax"


# ─────────────────────────── Sqoop ───────────────────────────

def test_sqoop_import_to_hdfs():
    r = migrate_file(DEMO / "04_sqoop_import.txt")
    assert r.ok and r.source_kind == "sqoop"
    conf = r.output_conf
    _hocon_ok(conf)
    assert "HdfsFile" in conf
    assert 'path = "/warehouse/ods/orders"' in conf
    assert "select order_id,user_id,amount,dt from orders" in conf
    assert "parallelism = 4" in conf             # -m 4


def test_sqoop_query_conditions_and_hive_import():
    r = migrate_sqoop(
        "sqoop import --connect jdbc:mysql://h:3306/db --username u "
        "--password p --query 'select * from t where $CONDITIONS' "
        "--hive-import --hive-table dwd.t")
    assert r.ok
    assert "where 1=1" in r.output_conf
    assert "Hive {" in r.output_conf
    kinds = {i.kind for i in r.issues}
    assert {"sqoop_conditions", "hive_sink_todo"} <= kinds


def test_sqoop_export():
    r = migrate_sqoop(
        "sqoop export --connect jdbc:mysql://h:3306/db --username u "
        "--password p --table target --export-dir /data/out -m 2")
    assert r.ok
    assert "HdfsFile" in r.output_conf.split("sink")[0]   # source side
    assert 'table = "target"' in r.output_conf
    _hocon_ok(r.output_conf)


def test_sqoop_unknown_flag_warns():
    r = migrate_sqoop(
        "sqoop import --connect jdbc:mysql://h/db --username u --password p "
        "--table t --direct")
    assert any(i.kind == "sqoop_flag_ignored" and "--direct" in i.params["flag"]
               for i in r.issues)


def test_migrate_text_dispatch():
    assert migrate_text('{"job": {}}').source_kind == "datax"
    assert migrate_text("sqoop import --table t").source_kind == "sqoop"
    r = migrate_text("SELECT 1")
    assert r.source_kind == "unknown" and not r.ok


# ─────────────────────────── batch / render / CLI ───────────────────────────

def test_migrate_dir_batch(tmp_path):
    b = migrate_dir(DEMO, out_dir=tmp_path)
    assert b.counts() == {"files": 4, "ok": 3, "failed": 1}
    assert b.worst_level() == "error"
    assert (tmp_path / "01_mysql_to_doris.conf").is_file()
    assert (tmp_path / "04_sqoop_import.conf").is_file()


def test_render_markdown_zh_en():
    r = migrate_file(DEMO / "01_mysql_to_doris.json")
    zh = render_migrate_markdown(r, "zh")
    assert "```hocon" in zh and "splitPk=order_id" in zh
    en = render_migrate_markdown(r, "en")
    assert "splitPk=order_id mapped" in en
    b = migrate_dir(DEMO)
    md = render_batch_markdown(b, "zh")
    assert "文件 4 · 成功 3 · 失败 1" in md


def test_cli_migrate_single_and_gate(tmp_path):
    out = tmp_path / "job.conf"
    res = runner.invoke(cli, [
        "migrate", str(DEMO / "01_mysql_to_doris.json"), "-o", str(out),
    ])
    assert res.exit_code == 0, res.output
    assert "Doris" in out.read_text(encoding="utf-8")
    gated = runner.invoke(cli, [
        "migrate", str(DEMO / "03_unknown_plugin.json"), "--fail-on", "error",
    ])
    assert gated.exit_code == 1


def test_cli_migrate_batch_json(tmp_path):
    res = runner.invoke(cli, [
        "migrate", "-D", str(DEMO), "-F", "json",
    ])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)
    assert data["stats"] == {"files": 4, "ok": 3, "failed": 1}
