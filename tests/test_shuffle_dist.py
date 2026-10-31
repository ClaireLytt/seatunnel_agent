"""Tests for the data_skew shuffle-distribution add-on (batch item 34)."""

from __future__ import annotations

from pathlib import Path

import pytest

from seatunnel_agent.agents.data.data_skew.shuffle_dist import (
    render_shuffle_dist,
    shuffle_distribution,
)

DEMO = (Path(__file__).resolve().parents[1] / "examples" / "dataskew_demo"
        / "eventlog_shuffle_dist.jsonl")


def test_fat_tail_detected_even_stage_silent():
    dists = shuffle_distribution(DEMO)
    by = {d.stage_id: d for d in dists}
    fat = by[3]
    assert fat.tasks == 23
    assert fat.p50 == 10_000_000
    # p99 lands on the hot tail, far above the median
    assert fat.p99 >= 380_000_000
    assert fat.ratio >= 38
    assert fat.verdict() == "confirmed"
    # the three hot tasks are named, hottest first
    assert [i for i, _ in fat.hot[:3]] == [20, 21, 22]
    even = by[5]
    assert even.ratio == pytest.approx(1.0)
    assert even.verdict() == "ok"
    # worst ratio sorts first
    assert dists[0].stage_id == 3


def test_render_zh_en():
    dists = shuffle_distribution(DEMO)
    zh = render_shuffle_dist(dists, "zh")
    en = render_shuffle_dist(dists, "en")
    assert "Shuffle 读分布" in zh and "确认" in zh and "#20" in zh
    assert "p99/p50" in en and "CONFIRMED" in en
    # the even stage is not listed among the flagged rows
    assert "ResultStage" not in en
    # hint explains the multi-hot-partition pattern
    assert "加盐" in zh and "salt" in en


def test_all_even_renders_ok(tmp_path):
    import json

    log = tmp_path / "even.jsonl"
    events = [{"Event": "SparkListenerTaskEnd", "Stage ID": 1,
               "Task Info": {"Index": i, "Launch Time": 0,
                             "Finish Time": 100},
               "Task Metrics": {"Shuffle Read Metrics": {
                   "Remote Bytes Read": 1000, "Local Bytes Read": 0}}}
              for i in range(5)]
    log.write_text("\n".join(json.dumps(e) for e in events),
                   encoding="utf-8")
    dists = shuffle_distribution(log)
    assert all(d.verdict() == "ok" for d in dists)
    assert "均匀" in render_shuffle_dist(dists, "zh")


def test_salt_what_if_minimal_and_fixed():
    from seatunnel_agent.agents.data.data_skew.shuffle_dist import (
        render_salt_what_if,
        salt_what_if,
    )

    dists = shuffle_distribution(DEMO)
    # auto mode finds the minimal healthy factor for the fat stage
    rows = salt_what_if(dists, 0)
    assert len(rows) == 1 and rows[0]["stage_id"] == 3
    auto = rows[0]
    assert auto["healthy"] and auto["factor"] >= 2
    assert auto["ratio_after"] < auto["ratio_before"]
    # one step below the minimal factor must still be skewed
    if auto["factor"] > 2:
        under = salt_what_if(dists, auto["factor"] - 1)[0]
        assert not under["healthy"]
    # a too-small explicit factor raises
    with pytest.raises(ValueError):
        salt_what_if(dists, 1)
    zh = render_salt_what_if(rows, "zh")
    en = render_salt_what_if(rows, "en")
    assert "加盐 what-if" in zh and f"x{auto['factor']}" in zh
    assert "Salt what-if" in en and "healthy" in en
    # nothing flagged -> nothing to salt
    assert "无需加盐" in render_salt_what_if([], "zh")


def test_skew_runtime_cli_salt_flag():
    from click.testing import CliRunner

    from seatunnel_agent.cli_cmds.skew import skew_runtime

    runner = CliRunner()
    res = runner.invoke(skew_runtime, [str(DEMO), "--shuffle-dist",
                                       "--what-if-salt", "0"])
    assert res.exit_code == 0 and "what-if" in res.output
    # --what-if-salt without --shuffle-dist is a usage error
    res = runner.invoke(skew_runtime, [str(DEMO), "--what-if-salt", "4"])
    assert res.exit_code == 2
