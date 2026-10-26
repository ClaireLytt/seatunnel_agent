"""Subscriptions CRUD + run-now sub-router."""

from __future__ import annotations

import threading
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .subscriptions import SubscriptionStore, run_subscription

router = APIRouter()

_sub_store = SubscriptionStore()


@router.get("/subscriptions")
def subscriptions_list() -> dict[str, Any]:
    return {"subscriptions": _sub_store.list()}


class SubscriptionCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    cron: str = Field(..., min_length=1)
    source_type: str = Field("metric")
    metric: str = ""
    favorite_id: str = ""
    ds_type: str = "hive"
    connection: str = ""
    database: str = ""
    webhook_url: str = ""
    lang: str = "zh"
    # metric_watch
    threshold_pct: float = 10.0
    watch_mode: str = "dod"
    # freshness
    max_lag_days: int = 1
    # digest
    metrics: list[str] = Field(default_factory=list)


@router.post("/subscriptions", status_code=201)
def subscriptions_create(req: SubscriptionCreateRequest) -> dict[str, Any]:
    try:
        entry = _sub_store.add(
            name=req.name,
            cron=req.cron,
            source_type=req.source_type,
            metric=req.metric,
            favorite_id=req.favorite_id,
            ds_type=req.ds_type,
            connection=req.connection,
            database=req.database,
            webhook_url=req.webhook_url,
            lang=req.lang,
            threshold_pct=req.threshold_pct,
            watch_mode=req.watch_mode,
            max_lag_days=req.max_lag_days,
            metrics=req.metrics,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"subscription": entry}


@router.delete("/subscriptions/{sub_id}")
def subscriptions_delete(sub_id: str) -> dict[str, Any]:
    if not _sub_store.delete(sub_id):
        raise HTTPException(status_code=404, detail="unknown subscription")
    return {"deleted": True}


class SubscriptionPatchRequest(BaseModel):
    enabled: bool


@router.patch("/subscriptions/{sub_id}")
def subscriptions_patch(sub_id: str, req: SubscriptionPatchRequest) -> dict[str, Any]:
    if not _sub_store.set_enabled(sub_id, req.enabled):
        raise HTTPException(status_code=404, detail="unknown subscription")
    return {"enabled": req.enabled}


@router.post("/subscriptions/{sub_id}/run")
def subscriptions_run(sub_id: str) -> dict[str, Any]:
    sub = _sub_store.get(sub_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="unknown subscription")

    result: dict[str, Any] = {"id": sub_id, "status": "pending"}

    def _run() -> None:
        try:
            outcome = run_subscription(sub)
            _sub_store.record_run(
                sub_id, outcome.get("status", "error"), outcome.get("error", ""),
            )
            if "alert_state" in outcome:
                _sub_store.record_alert_state(sub_id, outcome["alert_state"])
            result["status"] = outcome.get("status", "error")
            if outcome.get("error"):
                result["error"] = str(outcome["error"])[:500]
        except Exception as exc:
            result["status"] = "error"
            result["error"] = str(exc)[:500]

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=30)

    if t.is_alive():
        return {"id": sub_id, "status": "running", "message": "still executing"}
    return result
