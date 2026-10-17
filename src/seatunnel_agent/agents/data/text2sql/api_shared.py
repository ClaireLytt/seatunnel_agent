"""Shared state and helpers for text2sql API sub-routers."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from seatunnel_agent.common.config import load_settings

from .agent import Text2SQLAgent
from .executor import DS_TYPES, DatabaseConfig, create_executor
from .favorites import FavoritesStore
from .metrics import load_metric_store
from .schema import SchemaStore
from .sessions import SessionManager

_MAX_SESSIONS = 20
sessions = SessionManager()
fav_store = FavoritesStore()


def load_schema_store(
    ds_type: str,
    db_config_dict: dict[str, Any] | None,
    schema_ddl: str | None,
) -> tuple[SchemaStore, DatabaseConfig | None]:
    if ds_type not in DS_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported ds_type '{ds_type}'. Valid: {', '.join(DS_TYPES)}",
        )

    store: SchemaStore | None = None
    db_config: DatabaseConfig | None = None

    if db_config_dict:
        from .executor import DS_DEFAULTS
        defaults = DS_DEFAULTS.get(ds_type, {})
        try:
            db_config = DatabaseConfig(
                ds_type=ds_type,
                host=db_config_dict.get("host", "localhost"),
                port=int(db_config_dict.get("port", defaults.get("port", 0))),
                database=db_config_dict.get("database", str(defaults.get("database", "default"))),
                username=db_config_dict.get("username"),
                password=db_config_dict.get("password"),
            )
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid db_config: {exc}")
        executor = create_executor(db_config)
        store = SchemaStore.from_db(executor)

    if schema_ddl:
        from .schema import parse_ddl
        tables = parse_ddl(schema_ddl)
        if store is not None:
            wl_names = {t.full_name.lower() for t in tables}
            filtered = [tb for tb in store.tables if tb.full_name.lower() in wl_names]
            store = SchemaStore(filtered)
        else:
            store = SchemaStore(tables)

    if store is None or len(store) == 0:
        raise HTTPException(status_code=400, detail="No tables loaded — provide db_config or schema_ddl")
    return store, db_config


def build_agent(
    ds_type: str,
    db_config_dict: dict[str, Any] | None,
    schema_ddl: str | None,
    metrics_yaml: str | None = None,
) -> Text2SQLAgent:
    store, db_config = load_schema_store(ds_type, db_config_dict, schema_ddl)
    metric_store, metric_errors = load_metric_store(store, metrics_yaml)
    if metrics_yaml and metric_errors:
        raise HTTPException(
            status_code=400,
            detail="Invalid metrics_yaml: " + "; ".join(metric_errors),
        )
    return agent_from_store(store, ds_type, db_config, metric_store)


def agent_from_store(store, ds_type, db_config, metric_store) -> Text2SQLAgent:
    settings = load_settings()
    agent = Text2SQLAgent(
        settings, store=store, ds_type=ds_type, db_config=db_config,
        metric_store=metric_store if len(metric_store) else None,
    )
    agent.runtime.source = "api"
    return agent


def session_meta(session_id: str, agent: Text2SQLAgent) -> dict[str, Any]:
    tables = [t.full_name for t in agent.runtime.store.tables]
    return {
        "session_id": session_id,
        "ds_type": agent.runtime.ds_type,
        "table_count": len(tables),
        "tables": tables,
    }


def entry_or_404(session_id: str):
    entry = sessions.get(session_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="unknown session")
    return entry
