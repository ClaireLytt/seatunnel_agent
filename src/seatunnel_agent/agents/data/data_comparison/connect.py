"""Gradio-free per-side connect logic for the Data Comparison page.

Extracted from the legacy ``ui.py`` ``_do_connect`` closure so both the
Gradio page and the REST layer (``api.py``) share one implementation.
Takes a datasource *key* (not the dialect label) plus raw form strings,
resolves env/default fallbacks, opens the connection and stores the
executor + table list in the given :class:`SessionState`.
"""

from __future__ import annotations

from dataclasses import dataclass

from seatunnel_agent.agents.data.data_comparison.i18n import dc
from seatunnel_agent.agents.data.data_comparison.registry import SessionState
from seatunnel_agent.agents.data.data_comparison.ui_shared import _esc_html
from seatunnel_agent.agents.data.text2sql.executor import (
    DIALECT_NAMES,
    DS_DEFAULTS,
    ENV_PREFIX,
    DatabaseConfig,
    config_from_env,
    create_executor,
)


@dataclass
class ConnectResult:
    """Outcome of one per-side connect attempt."""

    ok: bool
    status: str = ""            # ✅-prefixed status line on success
    error: str = ""             # ❌-prefixed message on failure
    tables: list[str] | None = None
    resolved: DatabaseConfig | None = None  # config actually used


def connect_side(
    session: SessionState,
    side: str,
    ds_type: str,
    host: str | None,
    port: str | None,
    db: str | None,
    username: str | None,
    password: str | None,
    lang: str = "en",
) -> ConnectResult:
    """Connect one side ("a"/"b") and store executor + tables in *session*."""
    t = lambda k: dc(lang, k)

    if ds_type not in DS_DEFAULTS:
        return ConnectResult(ok=False, error=(
            f"❌ {t('dc_error')}: unknown datasource {_esc_html(str(ds_type))}"))

    h = (host or "").strip()
    p = (port or "").strip()
    d = (db or "").strip()
    u = (username or "").strip() or None
    pw = (password or "").strip() or None
    defaults = DS_DEFAULTS[ds_type]
    default_port = str(defaults["port"])
    default_db = defaults["database"]

    if ds_type == "sqlite":
        cfg = DatabaseConfig(
            ds_type="sqlite", host="", port=0,
            database=d or str(default_db),
        )
    else:
        if not h:
            fallback = config_from_env(ds_type)
            if fallback:
                h, p, d = fallback.host, str(fallback.port), fallback.database
                u, pw = fallback.username, fallback.password

        if not h:
            var = f"{ENV_PREFIX.get(ds_type, ds_type.upper())}_HOST"
            return ConnectResult(
                ok=False, error=f"❌ {t('dc_host_required').format(var=var)}")

        try:
            port_int = int(p or default_port)
        except ValueError:
            return ConnectResult(ok=False, error=f"❌ {t('dc_port_not_number')}")

        cfg = DatabaseConfig(
            ds_type=ds_type,
            host=h,
            port=port_int,
            database=d or str(default_db),
            username=u,
            password=pw,
        )

    try:
        executor = create_executor(cfg)
    except Exception as e:
        return ConnectResult(ok=False, error=f"❌ {_esc_html(str(e))}")
    ok, msg = executor.test_connection()
    if not ok:
        return ConnectResult(ok=False, error=f"❌ {_esc_html(msg)}")

    try:
        tables = executor.show_tables()
    except Exception as e:
        return ConnectResult(ok=False, error=f"❌ {_esc_html(str(e))}")

    with session.lock:
        setattr(session, f"executor_{side}", executor)
        setattr(session, f"tables_{side}", tables)

    dialect = DIALECT_NAMES.get(ds_type, ds_type)
    status = f"✅ {dialect} {msg} · {t('dc_tables_loaded').format(n=len(tables))}"
    return ConnectResult(ok=True, status=status, tables=tables, resolved=cfg)
