"""Row-level security policies — which ROWS leave the engine.

The validator guards which tables may be read and masking guards which
column values are shown; this layer injects per-table row filters into
every executed SELECT. Enforcement is server-side only: the active policy
comes from ``T2S_POLICY`` (a name defined in ``config/t2s_policies.yaml``
or ``T2S_POLICIES_PATH``), never from client input, and it is applied at
the executor factory — one choke point below chat, REST, MCP,
subscriptions, boards and reports alike.

.. code-block:: yaml

    policies:
      - name: app_only
        row_filters:
          dwd.orders: "channel = 'app'"
          dim.users: "region != 'internal'"

Fail-closed: with a policy active, SQL that sqlglot cannot parse is
rejected rather than executed unfiltered.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


class PolicyError(Exception):
    """Policy configuration or enforcement failure (fail closed)."""


_DEFAULT_POLICIES_FILE = "config/t2s_policies.yaml"


def _policies_path() -> Path:
    return Path(os.getenv("T2S_POLICIES_PATH", _DEFAULT_POLICIES_FILE))


def load_policies(path: str | Path | None = None) -> dict[str, dict[str, str]]:
    """{policy_name: {table: condition}} from the policies file ({} if absent)."""
    p = Path(path) if path is not None else _policies_path()
    if not p.is_file():
        return {}
    import yaml

    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    out: dict[str, dict[str, str]] = {}
    for item in raw.get("policies", []) or []:
        if not isinstance(item, dict):
            raise PolicyError("policies 条目必须是映射")
        name = str(item.get("name", "")).strip()
        filters_raw = item.get("row_filters") or {}
        if not name:
            raise PolicyError("policy 缺少 name")
        if not isinstance(filters_raw, dict) or not filters_raw:
            raise PolicyError(f"policy '{name}' 缺少 row_filters 映射")
        out[name] = {
            str(t).strip().lower(): str(c).strip()
            for t, c in filters_raw.items()
            if str(c).strip()
        }
    return out


def active_row_filters() -> dict[str, str] | None:
    """The row filters of the policy named by ``T2S_POLICY``, or None.

    Read at call time (long-lived servers and tests can repoint); naming a
    policy that the file does not define is a hard error, not a silent
    no-policy fallback.
    """
    name = os.getenv("T2S_POLICY", "").strip()
    if not name:
        return None
    policies = load_policies()
    if name not in policies:
        raise PolicyError(
            f"T2S_POLICY='{name}' 未在策略文件中定义"
            f"(已定义: {', '.join(sorted(policies)) or '无'})"
        )
    return policies[name]


def apply_row_filters(sql: str, filters: dict[str, str]) -> str:
    """AND each policy condition into every SELECT that reads its table.

    Conditions are written against the table's bare columns; they are
    qualified with the table's alias in place. Unparseable SQL raises
    :class:`PolicyError` — with a policy active we never run unfiltered.
    """
    import sqlglot
    from sqlglot import exp

    try:
        statements = sqlglot.parse(sql, error_level=sqlglot.ErrorLevel.RAISE)
    except Exception as exc:
        raise PolicyError(f"行级策略无法解析 SQL(拒绝执行): {exc}") from exc

    def _qualified(cond_sql: str, alias: str) -> Any:
        cond = sqlglot.parse_one(cond_sql)
        for col in cond.find_all(exp.Column):
            if col.table:  # already qualified in the policy file
                continue
            col.set("table", exp.to_identifier(alias))
        return cond

    rewritten: list[str] = []
    for stmt in statements:
        if stmt is None:
            continue
        for select in stmt.find_all(exp.Select):
            # tables read directly by THIS select (not nested subqueries)
            for table in select.find_all(exp.Table):
                if table.find_ancestor(exp.Select) is not select:
                    continue
                name = ".".join(
                    p for p in (table.db, table.name) if p
                ).lower()
                cond_sql = filters.get(name)
                if not cond_sql:
                    continue
                alias = table.alias or table.name
                select.where(_qualified(cond_sql, alias), copy=False)
        rewritten.append(stmt.sql())
    return ";\n".join(rewritten)


def wrap_executor(executor: Any) -> Any:
    """Enforce the active policy on every ``run`` of *executor* (identity
    pass-through when no policy is active)."""
    filters = active_row_filters()
    if filters is None or not filters:
        return executor
    row_filters: dict[str, str] = filters

    class _PolicyExecutor:
        """Thin proxy: rewrite, then delegate everything else."""

        def __init__(self, inner: Any) -> None:
            self._inner = inner

        def run(self, sql: str, **kwargs: Any) -> Any:
            return self._inner.run(
                apply_row_filters(sql, row_filters), **kwargs)

        def __getattr__(self, item: str) -> Any:
            return getattr(self._inner, item)

    return _PolicyExecutor(executor)
