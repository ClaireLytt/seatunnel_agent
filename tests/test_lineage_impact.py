# -*- coding: utf-8 -*-
"""Tests for the change impact analysis agent (data_lineage.impact).

Deterministic only — no LLM, no database, no network (git tests use a
throwaway local repository under tmp_path).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from seatunnel_agent.cli import cli
from seatunnel_agent.data_lineage.impact import (
    analyze_dirs,
    analyze_impact,
    impact_to_dict,
    materialize_git_ref,
    render_impact_markdown,
)
from seatunnel_agent.data_lineage.loaders import build_graph

runner = CliRunner()

DEMO = Path(__file__).resolve().parents[1] / "examples" / "impact_demo"
OLD, NEW = DEMO / "old", DEMO / "new"


def _demo_result(depth: int = 3):
    return analyze_dirs(OLD, NEW, depth=depth)


# ─────────────────────────── change detection ───────────────────────────

def test_demo_detects_all_three_change_kinds():
    r = _demo_result()
    assert r.counts() == {"changed": 3, "blast": 1,
                          "error": 1, "warn": 1, "info": 1}
    assert r.worst_level() == "error"
    by_table = {c.table: c for c in r.changed}
    assert by_table["ads.gmv_report"].level == "error"
    assert "dws.user_stats" in by_table["ads.gmv_report"].removed_upstreams
    assert by_table["dws.gmv_daily"].level == "warn"
    assert by_table["ads.channel_report"].level == "info"
    assert by_table["ads.channel_report"].is_new


def test_modified_expression_detected_with_old_and_new():
    r = _demo_result()
    gmv = next(c for c in r.changed if c.table == "dws.gmv_daily")
    mods = [cc for cc in gmv.column_changes if cc.kind == "modified"]
    assert len(mods) == 1
    assert mods[0].dst_column == "gmv"
    assert "refund_amount" in mods[0].new_expression
    assert "refund_amount" not in mods[0].old_expression


def test_downstream_blast_radius_and_depth():
    r = _demo_result()
    gmv = next(c for c in r.changed if c.table == "dws.gmv_daily")
    assert ("ads.gmv_report", 1) in gmv.downstream
    assert ("rpt.gmv_dashboard", 2) in gmv.downstream
    # depth=1 cuts the L2 table
    r1 = _demo_result(depth=1)
    gmv1 = next(c for c in r1.changed if c.table == "dws.gmv_daily")
    assert ("rpt.gmv_dashboard", 2) not in gmv1.downstream


def test_target_losing_its_producer_is_error(tmp_path):
    # dws.a is still referenced by ads.b in the new tree, but its own
    # producer file is gone: an upstream removal on dws.a, not a node removal.
    old = tmp_path / "old"; new = tmp_path / "new"
    old.mkdir(); new.mkdir()
    (old / "a.sql").write_text(
        "INSERT OVERWRITE TABLE dws.a SELECT x FROM ods.s;", encoding="utf-8")
    (old / "b.sql").write_text(
        "INSERT OVERWRITE TABLE ads.b SELECT x FROM dws.a;", encoding="utf-8")
    (new / "b.sql").write_text(
        "INSERT OVERWRITE TABLE ads.b SELECT x FROM dws.a;", encoding="utf-8")
    r = analyze_dirs(old, new)
    hit = next(c for c in r.changed if c.table == "dws.a")
    assert not hit.is_removed
    assert hit.removed_upstreams == ["ods.s"]
    assert hit.level == "error"
    assert ("ads.b", 1) in hit.downstream


def test_removed_table_walks_old_graph(tmp_path):
    # the whole subtree vanishes from the new tree: dws.a is a removed node
    # and its blast radius must come from the OLD graph.
    old = tmp_path / "old"; new = tmp_path / "new"
    old.mkdir(); new.mkdir()
    (old / "a.sql").write_text(
        "INSERT OVERWRITE TABLE dws.a SELECT x FROM ods.s;", encoding="utf-8")
    (old / "b.sql").write_text(
        "INSERT OVERWRITE TABLE ads.b SELECT x FROM dws.a;", encoding="utf-8")
    (new / "c.sql").write_text(
        "INSERT OVERWRITE TABLE dws.other SELECT x FROM ods.s;",
        encoding="utf-8")
    r = analyze_dirs(old, new)
    removed = next(c for c in r.changed if c.table == "dws.a")
    assert removed.is_removed
    assert removed.level == "error"           # ads.b consumed it in the old graph
    assert ("ads.b", 1) in removed.downstream


def test_removed_target_without_consumers_is_info(tmp_path):
    old = tmp_path / "old"; new = tmp_path / "new"
    old.mkdir(); new.mkdir()
    (old / "a.sql").write_text(
        "INSERT OVERWRITE TABLE dws.leaf SELECT x FROM ods.s;", encoding="utf-8")
    (new / "keep.sql").write_text(
        "INSERT OVERWRITE TABLE dws.other SELECT x FROM ods.s;", encoding="utf-8")
    r = analyze_dirs(old, new)
    leaf = next(c for c in r.changed if c.table == "dws.leaf")
    assert leaf.level == "info"


def test_no_change_yields_empty_result():
    old_graph, _ = build_graph(sql_dir=OLD, use_cache=False)
    new_graph, _ = build_graph(sql_dir=OLD, use_cache=False)
    r = analyze_impact(old_graph, new_graph)
    assert r.changed == []
    assert r.worst_level() is None
    md = render_impact_markdown(r, "zh")
    assert "完全一致" in md


def test_expression_normalization_avoids_false_positives(tmp_path):
    old = tmp_path / "old"; new = tmp_path / "new"
    old.mkdir(); new.mkdir()
    (old / "a.sql").write_text(
        "INSERT OVERWRITE TABLE dws.a SELECT SUM(amount) AS v "
        "FROM ods.s GROUP BY dt;", encoding="utf-8")
    # same logic, different whitespace/case
    (new / "a.sql").write_text(
        "INSERT OVERWRITE TABLE dws.a SELECT sum( amount )   AS v "
        "FROM ods.s GROUP BY dt;", encoding="utf-8")
    r = analyze_dirs(old, new)
    assert all(
        cc.kind != "modified"
        for c in r.changed for cc in c.column_changes
    )


# ─────────────────────────── rendering / payload ───────────────────────────

def test_render_markdown_zh_and_en():
    r = _demo_result()
    zh = render_impact_markdown(r, "zh")
    assert "变更影响分析" in zh and "字段口径变更" in zh and "上游被移除" in zh
    en = render_impact_markdown(r, "en")
    assert "Change Impact Analysis" in en
    assert "column expression changed" in en
    assert "upstream removed" in en


def test_impact_to_dict_payload():
    r = _demo_result()
    data = impact_to_dict(r, "zh")
    assert data["stats"]["error"] == 1
    assert "report" in data
    tables = {c["table"] for c in data["changed"]}
    assert {"ads.gmv_report", "dws.gmv_daily", "ads.channel_report"} <= tables


# ─────────────────────────── git mode ───────────────────────────

def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   capture_output=True, text=True)


def test_materialize_git_ref_matches_dir_mode(tmp_path):
    repo = tmp_path / "repo"
    (repo / "sql").mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    for f in OLD.glob("*.sql"):
        (repo / "sql" / f.name).write_text(
            f.read_text(encoding="utf-8"), encoding="utf-8")
    _git(repo, "add", "."); _git(repo, "commit", "-qm", "old")
    for f in (repo / "sql").glob("*.sql"):
        f.unlink()
    for f in NEW.glob("*.sql"):
        (repo / "sql" / f.name).write_text(
            f.read_text(encoding="utf-8"), encoding="utf-8")
    _git(repo, "add", "-A"); _git(repo, "commit", "-qm", "new")

    old_copy = materialize_git_ref("HEAD~1", "sql", repo_root=repo)
    try:
        r_git = analyze_dirs(old_copy, repo / "sql")
        r_dir = analyze_dirs(OLD, NEW)
        assert ({c.table: c.level for c in r_git.changed}
                == {c.table: c.level for c in r_dir.changed})
    finally:
        import shutil
        shutil.rmtree(old_copy, ignore_errors=True)


def test_materialize_git_ref_outside_repo_raises(tmp_path):
    with pytest.raises(RuntimeError):
        materialize_git_ref("HEAD", "sql", repo_root=tmp_path)


# ─────────────────────────── CLI ───────────────────────────

def test_cli_dir_mode_markdown():
    res = runner.invoke(cli, [
        "impact", "--old-dir", str(OLD), "--sql-dir", str(NEW),
    ])
    assert res.exit_code == 0, res.output
    assert "dws.gmv_daily" in res.output
    assert "ads.gmv_report" in res.output


def test_cli_json_mode():
    res = runner.invoke(cli, [
        "impact", "--old-dir", str(OLD), "--sql-dir", str(NEW), "-F", "json",
    ])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)
    assert data["stats"] == {"changed": 3, "blast": 1,
                             "error": 1, "warn": 1, "info": 1}


def test_cli_fail_on_gate():
    gated = runner.invoke(cli, [
        "impact", "--old-dir", str(OLD), "--sql-dir", str(NEW),
        "--fail-on", "error",
    ])
    assert gated.exit_code == 1
    clean = runner.invoke(cli, [
        "impact", "--old-dir", str(OLD), "--sql-dir", str(OLD),
        "--fail-on", "error",
    ])
    assert clean.exit_code == 0


def test_cli_requires_exactly_one_baseline():
    both_missing = runner.invoke(cli, ["impact", "--sql-dir", str(NEW)])
    assert both_missing.exit_code != 0
    assert "exactly one" in both_missing.output
    both_given = runner.invoke(cli, [
        "impact", "--sql-dir", str(NEW), "--old-dir", str(OLD),
        "--base", "HEAD",
    ])
    assert both_given.exit_code != 0


# ─────────────────────────── REST API ───────────────────────────

@pytest.fixture()
def api_client(monkeypatch):
    fastapi = pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from seatunnel_agent.data_lineage.api import router
    monkeypatch.setenv("LINEAGE_API_ALLOWED_DIRS", str(DEMO))
    app = fastapi.FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_impact(api_client):
    r = api_client.post("/api/lineage/impact", json={
        "old_dir": str(OLD), "new_dir": str(NEW),
    })
    assert r.status_code == 200
    data = r.json()
    assert data["stats"]["error"] == 1
    assert "变更影响分析" in data["report"]


def test_api_impact_whitelist(api_client, tmp_path):
    r = api_client.post("/api/lineage/impact", json={
        "old_dir": str(tmp_path), "new_dir": str(NEW),
    })
    assert r.status_code == 403


def test_materialize_git_ref_absolute_sql_dir(tmp_path):
    repo = tmp_path / "repo"
    (repo / "sql").mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "sql" / "a.sql").write_text(
        "INSERT OVERWRITE TABLE dws.a SELECT x FROM ods.s;", encoding="utf-8")
    _git(repo, "add", "."); _git(repo, "commit", "-qm", "v1")
    # absolute path must work the same as a relative one
    out = materialize_git_ref("HEAD", repo / "sql", repo_root=repo)
    try:
        assert (out / "a.sql").is_file()
    finally:
        import shutil
        shutil.rmtree(out, ignore_errors=True)


def test_materialize_git_ref_outside_toplevel_raises(tmp_path):
    repo = tmp_path / "repo"; other = tmp_path / "other"
    repo.mkdir(); other.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "a.sql").write_text("SELECT 1;", encoding="utf-8")
    _git(repo, "add", "."); _git(repo, "commit", "-qm", "v1")
    with pytest.raises(RuntimeError, match="outside the git repository"):
        materialize_git_ref("HEAD", other, repo_root=repo)


def test_materialize_git_ref_empty_baseline_marker(tmp_path):
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "docs" / "readme.md").write_text("x", encoding="utf-8")
    _git(repo, "add", "."); _git(repo, "commit", "-qm", "v1")
    (repo / "sql").mkdir()
    out = materialize_git_ref("HEAD", "sql", repo_root=repo)
    try:
        assert (out / ".impact_empty_baseline").is_file()
    finally:
        import shutil
        shutil.rmtree(out, ignore_errors=True)


def test_materialize_git_ref_from_repo_subdirectory(tmp_path):
    # regression: pathspecs are cwd-relative but ls-tree names are
    # toplevel-relative — running from a subdir used to yield an empty
    # baseline, silently turning breaking changes into "added/info".
    repo = tmp_path / "repo"
    (repo / "sql").mkdir(parents=True)
    (repo / "sub").mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "sql" / "a.sql").write_text(
        "INSERT OVERWRITE TABLE dws.a SELECT x FROM ods.s;", encoding="utf-8")
    _git(repo, "add", "."); _git(repo, "commit", "-qm", "v1")
    out = materialize_git_ref("HEAD", repo / "sql", repo_root=repo / "sub")
    try:
        assert (out / "a.sql").is_file()
        assert not (out / ".impact_empty_baseline").exists()
    finally:
        import shutil
        shutil.rmtree(out, ignore_errors=True)


def test_materialize_git_ref_cleans_tmp_on_failure(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "sql").mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "sql" / "a.sql").write_text("SELECT 1;", encoding="utf-8")
    _git(repo, "add", "."); _git(repo, "commit", "-qm", "v1")

    import seatunnel_agent.data_lineage.impact as impact_mod
    made: list[str] = []
    real_mkdtemp = impact_mod.tempfile.mkdtemp
    monkeypatch.setattr(impact_mod.tempfile, "mkdtemp",
                        lambda **kw: made.append(real_mkdtemp(**kw)) or made[-1])
    real_run = impact_mod.subprocess.run

    def failing_run(cmd, **kw):
        if "show" in cmd:
            class P:  # minimal failed-process stub
                returncode = 128
                stderr = "boom"
                stdout = ""
            return P()
        return real_run(cmd, **kw)

    monkeypatch.setattr(impact_mod.subprocess, "run", failing_run)
    with pytest.raises(RuntimeError, match="boom"):
        materialize_git_ref("HEAD", "sql", repo_root=repo)
    assert made and not Path(made[0]).exists()


def test_cli_utf8_stdio_helper(monkeypatch):
    # regression: emoji level markers crashed GBK consoles mid-report
    import io
    import sys as _sys
    from seatunnel_agent.cli import _ensure_utf8_stdio
    gbk_out = io.TextIOWrapper(io.BytesIO(), encoding="gbk")
    monkeypatch.setattr(_sys, "stdout", gbk_out)
    _ensure_utf8_stdio()
    assert _sys.stdout.encoding.lower().replace("-", "") == "utf8"
    _sys.stdout.write("❌ ⚠️ 变更影响")  # must not raise
    _sys.stdout.flush()


def test_api_impact_unreadable_dir_is_400(api_client, monkeypatch):
    # regression: non-ValueError build failures used to leak as HTTP 500
    import seatunnel_agent.data_lineage.impact as impact_mod

    def boom(*a, **kw):
        raise OSError("permission denied")

    monkeypatch.setattr(impact_mod, "analyze_dirs", boom)
    monkeypatch.setattr(
        "seatunnel_agent.data_lineage.api.analyze_dirs", boom, raising=False)
    r = api_client.post("/api/lineage/impact", json={
        "old_dir": str(OLD), "new_dir": str(NEW),
    })
    assert r.status_code == 400
    assert "变更影响分析失败" in r.json()["detail"]


# ─────────────────────────── MCP tool ───────────────────────────

def _mcp_tools(**kw):
    from seatunnel_agent.data_lineage.mcp_server import build_tool_functions
    return build_tool_functions(**kw)


def test_mcp_change_impact_with_old_dir():
    tools = _mcp_tools(sql_dir=str(NEW))
    out = tools["lineage_change_impact"](old_dir=str(OLD))
    assert "变更影响分析" in out
    assert "dws.gmv_daily" in out
    assert "error 1 / warn 1 / info 1" in out


def test_mcp_change_impact_requires_exactly_one_baseline():
    tools = _mcp_tools(sql_dir=str(NEW))
    assert "二选一" in tools["lineage_change_impact"]()
    assert "二选一" in tools["lineage_change_impact"](
        old_dir=str(OLD), base="HEAD")


def test_mcp_change_impact_needs_sql_dir():
    tools = _mcp_tools()
    assert "--sql-dir" in tools["lineage_change_impact"](old_dir=str(OLD))


def test_mcp_change_impact_bad_git_ref_is_message_not_crash(tmp_path):
    tools = _mcp_tools(sql_dir=str(tmp_path))
    out = tools["lineage_change_impact"](base="HEAD")
    assert "git 基线模式失败" in out


# ─────────────────────────── paste-two-snippets mode ───────────────────────────

OLD_SNIPPET = ("INSERT OVERWRITE TABLE dws.gmv_daily "
               "SELECT dt, SUM(amount) AS gmv FROM dwd.orders_di GROUP BY dt;")
NEW_SNIPPET = ("INSERT OVERWRITE TABLE dws.gmv_daily "
               "SELECT dt, SUM(amount - refund_amount) AS gmv "
               "FROM dwd.orders_di GROUP BY dt;")


def test_analyze_sql_texts_detects_expression_change():
    from seatunnel_agent.data_lineage.impact import analyze_sql_texts
    r = analyze_sql_texts(OLD_SNIPPET, NEW_SNIPPET)
    gmv = next(c for c in r.changed if c.table == "dws.gmv_daily")
    mods = [cc for cc in gmv.column_changes if cc.kind == "modified"]
    assert len(mods) == 1 and mods[0].dst_column == "gmv"
    # a single snippet has no downstream — drift without consumers is info
    assert gmv.level == "info"


def test_analyze_sql_texts_identical_is_clean():
    from seatunnel_agent.data_lineage.impact import analyze_sql_texts
    r = analyze_sql_texts(OLD_SNIPPET, OLD_SNIPPET)
    assert r.changed == [] and r.worst_level() is None


def test_analyze_sql_texts_requires_both_sides():
    from seatunnel_agent.data_lineage.impact import analyze_sql_texts
    with pytest.raises(ValueError, match="required"):
        analyze_sql_texts(OLD_SNIPPET, "   ")


def test_analyze_sql_texts_multi_statement_scripts():
    from seatunnel_agent.data_lineage.impact import analyze_sql_texts
    old = OLD_SNIPPET + "\nINSERT OVERWRITE TABLE ads.r SELECT gmv FROM dws.gmv_daily;"
    new = NEW_SNIPPET + "\nINSERT OVERWRITE TABLE ads.r SELECT gmv FROM dws.gmv_daily;"
    r = analyze_sql_texts(old, new)
    gmv = next(c for c in r.changed if c.table == "dws.gmv_daily")
    assert gmv.level == "warn"                 # now it has a consumer
    assert ("ads.r", 1) in gmv.downstream


def test_render_text_diff():
    from seatunnel_agent.data_lineage.impact import render_text_diff
    d = render_text_diff("SELECT 1", "SELECT 2")
    assert d.startswith("### SQL diff")
    assert "-SELECT 1" in d and "+SELECT 2" in d
    assert render_text_diff("SELECT 1", "SELECT 1") == ""


def test_api_impact_text_mode(api_client):
    r = api_client.post("/api/lineage/impact", json={
        "old_sql": OLD_SNIPPET, "new_sql": NEW_SNIPPET,
    })
    assert r.status_code == 200
    assert r.json()["stats"]["changed"] == 1


def test_api_impact_rejects_mixed_or_missing_modes(api_client):
    assert api_client.post("/api/lineage/impact", json={}).status_code == 400
    r = api_client.post("/api/lineage/impact", json={
        "old_dir": str(OLD), "new_dir": str(NEW),
        "old_sql": OLD_SNIPPET, "new_sql": NEW_SNIPPET,
    })
    assert r.status_code == 400
    assert "二选一" in r.json()["detail"]


# ─────────────────────────── context dir / mermaid / md-comment ───────────────────────────

def test_paste_mode_context_dir_reveals_real_downstream():
    from seatunnel_agent.data_lineage.impact import analyze_sql_texts
    # in isolation this drift is info (no visible consumers, see the
    # earlier test); with the repo context it must become warn with the
    # real downstream chain attached
    r = analyze_sql_texts(OLD_SNIPPET, NEW_SNIPPET, context_dir=OLD)
    gmv = next(c for c in r.changed if c.table == "dws.gmv_daily")
    assert gmv.level == "warn"
    down = dict(gmv.downstream)
    assert down.get("ads.gmv_report") == 1
    assert down.get("rpt.gmv_dashboard") == 2
    # the diff itself stays snippet-vs-snippet: exactly one changed table
    assert [c.table for c in r.changed] == ["dws.gmv_daily"]


def test_paste_mode_context_dir_must_exist():
    from seatunnel_agent.data_lineage.impact import analyze_sql_texts
    with pytest.raises(ValueError, match="context SQL directory"):
        analyze_sql_texts(OLD_SNIPPET, NEW_SNIPPET, context_dir="no_such_ctx")


def test_render_impact_mermaid():
    from seatunnel_agent.data_lineage.impact import render_impact_mermaid
    r = _demo_result()
    src = render_impact_mermaid(r)
    assert src.startswith("flowchart LR")
    assert 'n_dws_gmv_daily["dws.gmv_daily"]:::warn' in src
    assert 'n_ads_gmv_report["ads.gmv_report"]:::error' in src
    assert ":::blast" in src            # rpt.gmv_dashboard, downstream-only
    assert "n_dws_gmv_daily --> n_ads_gmv_report" in src
    assert "classDef error" in src
    # clean result renders nothing
    from seatunnel_agent.data_lineage.impact import analyze_sql_texts
    clean = analyze_sql_texts(OLD_SNIPPET, OLD_SNIPPET)
    assert render_impact_mermaid(clean) == ""


def test_render_impact_comment():
    from seatunnel_agent.data_lineage.impact import render_impact_comment
    r = _demo_result()
    md = render_impact_comment(r, "zh")
    assert md.startswith("**变更影响**")
    assert "| `dws.gmv_daily` | warn |" in md
    assert "rpt.gmv_dashboard" in md
    en = render_impact_comment(r, "en")
    assert en.startswith("**Change Impact**")
    from seatunnel_agent.data_lineage.impact import analyze_sql_texts
    clean = analyze_sql_texts(OLD_SNIPPET, OLD_SNIPPET)
    assert "✅" in render_impact_comment(clean, "zh")


def test_cli_md_comment_format():
    res = runner.invoke(cli, [
        "impact", "--old-dir", str(OLD), "--sql-dir", str(NEW),
        "-F", "md-comment",
    ])
    assert res.exit_code == 0, res.output
    assert res.output.startswith("**变更影响**")
    assert "| `ads.gmv_report` | error |" in res.output


def test_api_impact_context_dir(api_client):
    r = api_client.post("/api/lineage/impact", json={
        "old_sql": OLD_SNIPPET, "new_sql": NEW_SNIPPET,
        "context_dir": str(OLD),
    })
    assert r.status_code == 200
    changed = r.json()["changed"]
    assert changed[0]["level"] == "warn"


def test_api_impact_context_dir_whitelisted(api_client, tmp_path):
    r = api_client.post("/api/lineage/impact", json={
        "old_sql": OLD_SNIPPET, "new_sql": NEW_SNIPPET,
        "context_dir": str(tmp_path),
    })
    assert r.status_code == 403


def test_materialize_git_ref_non_ascii_filenames(tmp_path):
    # regression: git C-quotes non-ASCII paths ("\346..."), the .sql suffix
    # check dropped them and their breaking changes passed --fail-on error
    repo = tmp_path / "repo"
    (repo / "sql").mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "sql" / "报表统计.sql").write_text(
        "INSERT OVERWRITE TABLE dws.a SELECT x FROM ods.s;", encoding="utf-8")
    (repo / "sql" / "plain.sql").write_text(
        "INSERT OVERWRITE TABLE dws.b SELECT x FROM ods.s;", encoding="utf-8")
    _git(repo, "add", "."); _git(repo, "commit", "-qm", "v1")
    out = materialize_git_ref("HEAD", "sql", repo_root=repo)
    try:
        assert (out / "plain.sql").is_file()
        assert (out / "报表统计.sql").is_file()
        assert "INSERT OVERWRITE" in (out / "报表统计.sql").read_text(
            encoding="utf-8")
        assert not (out / ".impact_empty_baseline").exists()
    finally:
        import shutil
        shutil.rmtree(out, ignore_errors=True)


def test_mermaid_draws_only_real_edges():
    # regression: depth-bucket guessing fabricated cross-branch edges —
    # the demo rendered ads.channel_report --> rpt.gmv_dashboard although
    # rpt.gmv_dashboard reads from ads.gmv_report
    from seatunnel_agent.data_lineage.impact import render_impact_mermaid
    src = render_impact_mermaid(_demo_result())
    assert "n_ads_gmv_report --> n_rpt_gmv_dashboard" in src
    assert "n_ads_channel_report --> n_rpt_gmv_dashboard" not in src
    gmv = next(c for c in _demo_result().changed
               if c.table == "dws.gmv_daily")
    assert ("ads.gmv_report", "rpt.gmv_dashboard") in gmv.downstream_edges


# ─────────────────────────── analysis history (impact-stats) ───────────────────────────

def test_impact_logger_roundtrip(tmp_path):
    from seatunnel_agent.data_lineage.impact import ImpactLogger
    lg = ImpactLogger(tmp_path)
    r = _demo_result()
    lg.log_impact(r, mode="dirs", source="cli", baseline=str(OLD))
    lg.log_impact(r, mode="text", source="ui", baseline="<pasted>")
    recs = lg.recent(10)
    assert len(recs) == 2
    assert recs[0]["worst"] == "error"
    assert recs[0]["stats"]["changed"] == 3
    assert "dws.gmv_daily" in recs[0]["tables"]
    assert recs[1]["mode"] == "text"


def test_cli_impact_writes_history(tmp_path, monkeypatch):
    import seatunnel_agent.data_lineage.impact as impact_mod
    made = []
    orig = impact_mod.ImpactLogger

    class Spy(orig):
        def __init__(self, log_dir="logs"):
            super().__init__(tmp_path)
        def log_impact(self, *a, **kw):
            made.append(kw.get("mode") or a[1])
            super().log_impact(*a, **kw)

    monkeypatch.setattr(impact_mod, "ImpactLogger", Spy)
    res = runner.invoke(cli, [
        "impact", "--old-dir", str(OLD), "--sql-dir", str(NEW),
    ])
    assert res.exit_code == 0, res.output
    assert made == ["dirs"]
    assert (tmp_path / "impact.jsonl").is_file()


def test_cli_impact_stats_summary(tmp_path, monkeypatch):
    import threading

    import seatunnel_agent.data_lineage.impact as impact_mod

    lg = impact_mod.ImpactLogger(tmp_path)
    lg.log_impact(_demo_result(), mode="git", source="cli", baseline="HEAD~1")

    # point the default logger at tmp_path
    def fake_init(self, log_dir="logs"):
        self.log_dir = Path(tmp_path)
        self.log_file = self.log_dir / "impact.jsonl"
        self._lock = threading.Lock()

    monkeypatch.setattr(impact_mod.ImpactLogger, "__init__", fake_init)
    res = runner.invoke(cli, ["impact-stats"])
    assert res.exit_code == 0, res.output
    assert "共 1 次" in res.output
    assert "含破坏性 1 次" in res.output
    assert "高频变更表" in res.output
