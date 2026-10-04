"""Tests for sensitive-column masking at presentation edges."""

from __future__ import annotations

import json
import sqlite3


from seatunnel_agent.text2sql.masking import (
    apply_masking,
    mask_value,
    sensitive_kind,
)


def test_sensitive_kind_detection() -> None:
    assert sensitive_kind("mobile") == "phone"
    assert sensitive_kind("user_phone") == "phone"
    assert sensitive_kind("联系电话") == "phone"
    assert sensitive_kind("id_card") == "id"
    assert sensitive_kind("身份证号") == "id"
    assert sensitive_kind("email") == "email"
    assert sensitive_kind("邮箱") == "email"
    assert sensitive_kind("bank_card") == "bank"
    assert sensitive_kind("card_no") == "bank"
    assert sensitive_kind("city") is None
    assert sensitive_kind("amount") is None
    # "hotel" must not trip the tel pattern
    assert sensitive_kind("hotel") is None


def test_extra_columns_env(monkeypatch) -> None:
    monkeypatch.setenv("T2S_MASK_COLUMNS", "secret_col, another")
    assert sensitive_kind("secret_col") == "generic"
    assert sensitive_kind("Another") == "generic"
    monkeypatch.delenv("T2S_MASK_COLUMNS")
    assert sensitive_kind("secret_col") is None


def test_mask_value_shapes() -> None:
    assert mask_value("13812345678", "phone") == "138****78"
    assert mask_value("110101199001011234", "id") == "1101***********234"
    assert mask_value("alice@example.com", "email") == "a***@example.com"
    assert mask_value("6222020200112233", "bank") == "6222********2233"
    assert mask_value("abcdef", "generic") == "a****f"
    assert mask_value("ab", "generic") == "**"
    assert mask_value(None, "phone") is None


def test_apply_masking(monkeypatch) -> None:
    monkeypatch.delenv("T2S_MASKING", raising=False)
    cols = ["name", "mobile", "amount"]
    rows = [("张三", "13812345678", 10.0), ("李四", "13987654321", 20.0)]
    masked, masked_cols = apply_masking(cols, rows)
    assert masked_cols == ["mobile"]
    assert masked[0] == ("张三", "138****78", 10.0)

    # kill switch
    monkeypatch.setenv("T2S_MASKING", "0")
    same, none_masked = apply_masking(cols, rows)
    assert same is rows and none_masked == []


def test_apply_masking_no_sensitive_is_noop() -> None:
    cols = ["city", "amount"]
    rows = [("SH", 1)]
    same, masked_cols = apply_masking(cols, rows)
    assert same is rows and masked_cols == []


def test_execute_sql_masks_preview(tmp_path, monkeypatch) -> None:
    from seatunnel_agent.text2sql.executor import DatabaseConfig
    from seatunnel_agent.text2sql.schema import SchemaStore, parse_ddl
    from seatunnel_agent.text2sql.tools import (
        Text2SQLRuntime,
        execute_text2sql_tool,
    )

    monkeypatch.delenv("T2S_MASKING", raising=False)
    db = tmp_path / "m.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE users(name TEXT, mobile TEXT)")
    conn.execute("INSERT INTO users VALUES ('张三', '13812345678')")
    conn.commit()
    conn.close()
    store = SchemaStore(parse_ddl(
        "CREATE TABLE users(name string COMMENT 'n', mobile string COMMENT '手机号') COMMENT 'u';"
    ))
    rt = Text2SQLRuntime(
        store=store, ds_type="sqlite",
        db_config=DatabaseConfig(ds_type="sqlite", host="", port=0, database=str(db)),
    )
    out = json.loads(execute_text2sql_tool("execute_sql", {
        "sql": "SELECT name, mobile FROM users",
    }, rt))
    assert out.get("success"), out
    assert out["masked_columns"] == ["mobile"]
    assert out["preview_rows"][0][1] == "138****78"
    # raw values stay intact inside the runtime (charts/diff/attribution)
    assert rt.last_result.rows[0][1] == "13812345678"

    # export path masks too
    out2 = json.loads(execute_text2sql_tool("export_csv", {
        "path": str(tmp_path / "out.csv"),
    }, rt))
    assert out2.get("success"), out2
    content = (tmp_path / "out.csv").read_text(encoding="utf-8-sig")
    assert "13812345678" not in content and "138****78" in content


def test_subscription_card_masks(monkeypatch) -> None:
    monkeypatch.delenv("T2S_MASKING", raising=False)
    from seatunnel_agent.text2sql.subscriptions import render_card_markdown

    md = render_card_markdown(["mobile"], [("13812345678",)])
    assert "13812345678" not in md and "138****78" in md
