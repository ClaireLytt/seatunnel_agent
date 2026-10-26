"""Row-level policy tests: rewrite correctness, bypass surface, the
executor choke point, and chat end-to-end on sqlite."""

from __future__ import annotations

import sqlite3

import pytest

pytest.importorskip("yaml")
pytest.importorskip("sqlglot")

from seatunnel_agent.agents.data.text2sql.policies import (
    PolicyError,
    active_row_filters,
    apply_row_filters,
    load_policies,
)

_FILTERS = {"dwd.orders": "channel = 'app'"}


def _norm(sql: str) -> str:
    return " ".join(sql.split()).lower()


class TestRewrite:
    def test_simple_select(self) -> None:
        out = apply_row_filters("SELECT * FROM dwd.orders", _FILTERS)
        assert "channel = 'app'" in out.lower()
        assert "where" in out.lower()

    def test_alias_qualified(self) -> None:
        out = apply_row_filters(
            "SELECT o.id FROM dwd.orders o WHERE o.id > 5", _FILTERS)
        assert "o.channel = 'app'" in _norm(out)
        assert "o.id > 5" in _norm(out)  # 原条件保留(AND)

    def test_join_both_tables_filtered(self) -> None:
        out = apply_row_filters(
            "SELECT * FROM dwd.orders o JOIN dim.users u ON o.uid = u.id",
            {"dwd.orders": "channel = 'app'", "dim.users": "region = 'cn'"},
        )
        n = _norm(out)
        assert "o.channel = 'app'" in n and "u.region = 'cn'" in n

    def test_subquery_filtered(self) -> None:
        out = apply_row_filters(
            "SELECT * FROM (SELECT id FROM dwd.orders) t", _FILTERS)
        assert "channel = 'app'" in _norm(out)

    def test_union_both_arms(self) -> None:
        out = apply_row_filters(
            "SELECT id FROM dwd.orders UNION ALL SELECT id FROM dwd.orders",
            _FILTERS,
        )
        assert _norm(out).count("channel = 'app'") == 2

    def test_unrelated_table_untouched(self) -> None:
        sql = "SELECT * FROM dim.other"
        assert _norm(apply_row_filters(sql, _FILTERS)) == _norm(sql)

    def test_unparseable_fails_closed(self) -> None:
        with pytest.raises(PolicyError):
            apply_row_filters("SELECT FROM WHERE !!!", _FILTERS)


class TestConfig:
    def test_load_and_activate(self, tmp_path, monkeypatch) -> None:
        f = tmp_path / "p.yaml"
        f.write_text(
            "policies:\n"
            "  - name: app_only\n"
            "    row_filters:\n"
            "      dwd.orders: \"channel = 'app'\"\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("T2S_POLICIES_PATH", str(f))
        assert load_policies()["app_only"]["dwd.orders"] == "channel = 'app'"
        monkeypatch.setenv("T2S_POLICY", "app_only")
        assert active_row_filters() == {"dwd.orders": "channel = 'app'"}
        # 指向未定义策略 = 硬错误,不静默放行
        monkeypatch.setenv("T2S_POLICY", "nope")
        with pytest.raises(PolicyError):
            active_row_filters()
        monkeypatch.delenv("T2S_POLICY")
        assert active_row_filters() is None


def test_policy_enforced_end_to_end(tmp_path, monkeypatch) -> None:
    """execute_sql 全链路:策略激活后只见 app 渠道的行."""
    import json

    from seatunnel_agent.agents.data.text2sql.executor import (
        DatabaseConfig,
        create_executor,
    )
    from seatunnel_agent.agents.data.text2sql.runtime import Text2SQLRuntime
    from seatunnel_agent.agents.data.text2sql.schema import SchemaStore, parse_ddl
    from seatunnel_agent.agents.data.text2sql.tools import execute_text2sql_tool

    db = tmp_path / "p.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE orders (id INTEGER, amount REAL, channel TEXT)")
    con.executemany("INSERT INTO orders VALUES (?,?,?)", [
        (1, 10.0, "app"), (2, 20.0, "web"), (3, 30.0, "app"),
    ])
    con.commit()
    con.close()
    f = tmp_path / "p.yaml"
    f.write_text(
        "policies:\n"
        "  - name: app_only\n"
        "    row_filters:\n"
        "      orders: \"channel = 'app'\"\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("T2S_POLICIES_PATH", str(f))
    monkeypatch.setenv("T2S_POLICY", "app_only")

    rt = Text2SQLRuntime(
        store=SchemaStore(parse_ddl(
            "CREATE TABLE orders (id int, amount double, channel string);")),
        ds_type="sqlite",
        db_config=DatabaseConfig(ds_type="sqlite", host="", port=0,
                                 database=str(db)),
    )
    out = json.loads(execute_text2sql_tool(
        "execute_sql", {"sql": "SELECT SUM(amount) AS s FROM orders"}, rt))
    assert out.get("success"), out
    assert out["preview_rows"][0][0] == 40.0  # 10+30,web 的 20 被过滤

    # 关掉策略(新执行器)看到全量 — 证明过滤确实来自策略层
    monkeypatch.delenv("T2S_POLICY")
    executor = create_executor(rt.db_config)
    result = executor.run("SELECT SUM(amount) FROM orders", max_rows=5)
    assert result.rows[0][0] == 60.0
