"""Tests for push-channel dispatch (feishu/dingtalk/wecom/email) and the
pinned-query boards."""

from __future__ import annotations

import sqlite3

import pytest

from seatunnel_agent.text2sql.boards import BoardStore, render_board
from seatunnel_agent.text2sql.subscriptions import (
    detect_channel,
    push_card,
    push_dingtalk,
    push_wecom,
)

# ----------------------------------------------------------------------
# Channel dispatch
# ----------------------------------------------------------------------


def test_detect_channel() -> None:
    assert detect_channel("https://open.feishu.cn/open-apis/bot/v2/hook/x") == "feishu"
    assert detect_channel("https://oapi.dingtalk.com/robot/send?access_token=x") == "dingtalk"
    assert detect_channel("https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=x") == "wecom"
    assert detect_channel("mailto:a@b.com") == "email"
    assert detect_channel("a@b.com") == "email"
    assert detect_channel("https://unknown.example.com/hook") == "feishu"  # default


def _mock_post(captured: list, response: dict):
    def _fake(url, payload, timeout):
        captured.append((url, payload))
        return True, response
    return _fake


def test_push_dingtalk_payload(monkeypatch) -> None:
    from seatunnel_agent.text2sql import subscriptions as subs

    captured: list = []
    monkeypatch.setattr(subs, "_post_json", _mock_post(captured, {"errcode": 0}))
    ok, msg = push_dingtalk("https://oapi.dingtalk.com/robot/send", "日报", "a | b", ok=True)
    assert ok and msg == "ok"
    url, payload = captured[0]
    assert payload["msgtype"] == "markdown"
    assert payload["markdown"]["title"] == "日报"
    assert "a | b" in payload["markdown"]["text"]

    monkeypatch.setattr(subs, "_post_json",
                        _mock_post(captured, {"errcode": 310000, "errmsg": "sign not match"}))
    ok, msg = push_dingtalk("https://oapi.dingtalk.com/robot/send", "日报", "x")
    assert not ok and "sign not match" in msg


def test_push_wecom_payload_and_truncation(monkeypatch) -> None:
    from seatunnel_agent.text2sql import subscriptions as subs

    captured: list = []
    monkeypatch.setattr(subs, "_post_json", _mock_post(captured, {"errcode": 0}))
    ok, _ = push_wecom("https://qyapi.weixin.qq.com/x", "周报", "行" * 5000)
    assert ok
    _url, payload = captured[0]
    assert len(payload["markdown"]["content"].encode("utf-8")) <= 4000


def test_push_card_dispatches(monkeypatch) -> None:
    from seatunnel_agent.text2sql import subscriptions as subs

    calls: list[str] = []

    def _make(name):
        def _fake(url, title, body, ok=True, timeout=15, img_key=""):
            calls.append(name)
            return True, "ok"
        return _fake

    monkeypatch.setitem(subs._CHANNEL_PUSHERS, "feishu", _make("feishu"))
    monkeypatch.setitem(subs._CHANNEL_PUSHERS, "dingtalk", _make("dingtalk"))
    monkeypatch.setitem(subs._CHANNEL_PUSHERS, "wecom", _make("wecom"))
    monkeypatch.setitem(subs._CHANNEL_PUSHERS, "email", _make("email"))

    push_card("https://open.feishu.cn/hook", "t", "b")
    push_card("https://oapi.dingtalk.com/robot/send", "t", "b")
    push_card("https://qyapi.weixin.qq.com/hook", "t", "b")
    push_card("mailto:a@b.com", "t", "b")
    assert calls == ["feishu", "dingtalk", "wecom", "email"]


def test_push_email_requires_smtp_host(monkeypatch) -> None:
    from seatunnel_agent.text2sql.subscriptions import push_email

    monkeypatch.delenv("SMTP_HOST", raising=False)
    ok, msg = push_email("mailto:a@b.com", "t", "b")
    assert not ok and "SMTP_HOST" in msg


# ----------------------------------------------------------------------
# Boards
# ----------------------------------------------------------------------


@pytest.fixture()
def store(tmp_path) -> BoardStore:
    return BoardStore(tmp_path / "boards.json")


def test_board_crud(store: BoardStore) -> None:
    b = store.create("经营日报")
    assert store.get(b["id"])["name"] == "经营日报"
    assert store.get_by_name("经营日报") is not None
    with pytest.raises(ValueError, match="已存在"):
        store.create("经营日报")
    with pytest.raises(ValueError):
        store.create("   ")
    assert store.delete(b["id"]) is True
    assert store.delete(b["id"]) is False


def test_board_pin_unpin(store: BoardStore) -> None:
    b = store.create("看板A")
    item = store.pin(b["id"], title="各城市销售额", sql="SELECT city FROM sales",
                     ds_type="sqlite")
    assert item["title"] == "各城市销售额"
    board = store.get(b["id"])
    assert len(board["items"]) == 1
    assert store.unpin(b["id"], item["id"]) is True
    assert store.unpin(b["id"], item["id"]) is False
    with pytest.raises(ValueError, match="不存在"):
        store.pin("nope", title="x", sql="SELECT 1")
    with pytest.raises(ValueError):
        store.pin(b["id"], title="x", sql="  ")


def test_render_board_sqlite(store: BoardStore, tmp_path) -> None:
    from seatunnel_agent.text2sql.executor import DatabaseConfig, create_executor
    from seatunnel_agent.text2sql.schema import SchemaStore, parse_ddl

    db = tmp_path / "b.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE sales(city TEXT, amount REAL)")
    conn.executemany("INSERT INTO sales VALUES (?,?)",
                     [("SH", 10.0), ("BJ", 20.0)])
    conn.commit()
    conn.close()

    schema_store = SchemaStore(parse_ddl(
        "CREATE TABLE sales(city string COMMENT 'c', amount double COMMENT 'a') COMMENT 's';"
    ))
    executor = create_executor(
        DatabaseConfig(ds_type="sqlite", host="", port=0, database=str(db))
    )

    b = store.create("测试板")
    store.pin(b["id"], title="按城市", sql="SELECT city, SUM(amount) AS amt FROM sales GROUP BY city")
    store.pin(b["id"], title="被拒", sql="DELETE FROM sales")  # must be rejected, not run
    store.pin(b["id"], title="坏SQL", sql="SELECT nope FROM sales")

    entries = render_board(store.get(b["id"]), executor, schema_store, ds_type="sqlite")
    assert len(entries) == 3
    ok_entry = entries[0]
    assert ok_entry.get("error") is None
    assert ok_entry["row_count"] == 2
    assert entries[1]["error"] and "rejected" in entries[1]["error"].lower() or "rejected" in entries[1]["error"]
    assert entries[2]["error"]  # execution error captured, not raised

    # the DELETE must never have executed
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 2
    conn.close()


def test_board_corrupt_file(tmp_path) -> None:
    p = tmp_path / "x.json"
    p.write_text("{oops", encoding="utf-8")
    assert BoardStore(p).list() == []
