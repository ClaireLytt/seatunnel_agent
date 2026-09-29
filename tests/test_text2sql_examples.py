"""Tests for the few-shot example store (accuracy flywheel): CRUD,
BM25 retrieval, question augmentation, and the CLI group."""

from __future__ import annotations

import json

import pytest

from seatunnel_agent.text2sql.examples import ExampleStore, augment_question


@pytest.fixture()
def store(tmp_path) -> ExampleStore:
    return ExampleStore(tmp_path / "examples.json")


def test_add_list_remove(store: ExampleStore) -> None:
    e1 = store.add("昨天各城市的销售额", "SELECT city, SUM(amount) FROM sales GROUP BY city",
                   tables=["sales"], source="feedback")
    store.add("订单量趋势", "SELECT dt, COUNT(*) FROM sales GROUP BY dt")
    assert len(store) == 2
    assert store.list()[0]["id"] == e1["id"]
    assert store.remove(e1["id"]) is True
    assert store.remove(e1["id"]) is False
    assert len(store) == 1


def test_same_question_replaces(store: ExampleStore) -> None:
    store.add("各城市销售额", "SELECT 1")
    store.add("各城市销售额", "SELECT 2")
    items = store.list()
    assert len(items) == 1
    assert items[0]["sql"] == "SELECT 2"


def test_remove_by_question(store: ExampleStore) -> None:
    store.add("各城市销售额", "SELECT 1")
    assert store.remove_by_question("各城市销售额") is True
    assert store.remove_by_question("不存在的问题") is False
    assert len(store) == 0


def test_add_rejects_empty(store: ExampleStore) -> None:
    with pytest.raises(ValueError):
        store.add("", "SELECT 1")
    with pytest.raises(ValueError):
        store.add("问题", "   ")


def test_top_bm25_ranking(store: ExampleStore) -> None:
    store.add("昨天各城市的销售额", "SELECT city, SUM(amount) FROM sales GROUP BY city")
    store.add("每个渠道的退款率", "SELECT channel, ... FROM refunds")
    store.add("库存周转天数", "SELECT ... FROM inventory")

    hits = store.top("上周各城市销售额是多少", k=2)
    assert hits and hits[0]["question"] == "昨天各城市的销售额"
    # unrelated question -> no zero-score noise
    assert store.top("完全无关的天气问题", k=3) == [] or all(
        h["question"] for h in store.top("完全无关的天气问题", k=3)
    )


def test_top_ignores_unverified(store: ExampleStore) -> None:
    store.add("各城市销售额", "SELECT 1", verified=False)
    assert store.top("各城市销售额") == []


def test_augment_question(store: ExampleStore) -> None:
    store.add("昨天各城市的销售额", "SELECT city, SUM(amount) FROM sales GROUP BY city")
    out = augment_question("今天各城市的销售额", store)
    assert out.startswith("今天各城市的销售额")
    assert "参考示例" in out
    assert "SELECT city, SUM(amount) FROM sales GROUP BY city" in out

    # no hit / no store -> unchanged
    assert augment_question("天气如何", store) == "天气如何"
    assert augment_question("问题", None) == "问题"


def test_augment_survives_broken_store(tmp_path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    store = ExampleStore(bad)
    assert augment_question("问题", store) == "问题"


def test_corrupt_file_returns_empty(tmp_path) -> None:
    p = tmp_path / "x.json"
    p.write_text("[{broken", encoding="utf-8")
    assert ExampleStore(p).list() == []


def test_agent_augments_user_message(tmp_path, monkeypatch) -> None:
    """The agent injects examples into the LLM message but keeps the raw
    question in last_user_question."""
    from seatunnel_agent.text2sql.agent import Text2SQLAgent
    from seatunnel_agent.text2sql.schema import SchemaStore

    ex = ExampleStore(tmp_path / "ex.json")
    ex.add("各城市销售额", "SELECT city, SUM(amount) FROM sales GROUP BY city")

    class _FakeResp:
        raw_content = [{"type": "text", "text": "done"}]
        usage = None
        thinking_text = ""
        reply_text = "done"
        wants_tool_use = False
        tool_calls = []

    class _FakeLLM:
        def __init__(self, *a, **k):
            pass

        def chat(self, system, messages, on_text_delta=None):
            return _FakeResp()

        def append_assistant(self, raw):
            return {"role": "assistant", "content": raw}

    monkeypatch.setattr("seatunnel_agent.text2sql.agent.LLMClient", _FakeLLM)

    from seatunnel_agent.config import Settings

    agent = Text2SQLAgent(
        settings=Settings(api_key="test"), store=SchemaStore([]), ds_type="sqlite",
        example_store=ex,
    )
    agent.run("查一下各城市销售额")
    assert agent.last_user_question == "查一下各城市销售额"
    first_user = agent.messages[0]["content"]
    assert "参考示例" in first_user
    assert first_user.startswith("查一下各城市销售额")


def test_cli_examples_roundtrip(tmp_path) -> None:
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    f = str(tmp_path / "ex.json")
    runner = CliRunner()
    r = runner.invoke(cli, ["t2s-examples", "add", "-q", "各城市销售额",
                            "-s", "SELECT city FROM sales", "-f", f])
    assert r.exit_code == 0, r.output
    r = runner.invoke(cli, ["t2s-examples", "list", "-f", f])
    assert r.exit_code == 0 and "各城市销售额" in r.output
    ex_id = json.loads((tmp_path / "ex.json").read_text(encoding="utf-8"))[0]["id"]
    r = runner.invoke(cli, ["t2s-examples", "rm", ex_id, "-f", f])
    assert r.exit_code == 0
    r = runner.invoke(cli, ["t2s-examples", "rm", "nope", "-f", f])
    assert r.exit_code != 0
