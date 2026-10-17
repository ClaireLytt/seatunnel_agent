"""Favorites CRUD + feedback flywheel sub-router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .api_shared import fav_store, sessions
from .examples import ExampleStore
from .validator import extract_tables

router = APIRouter()


class FavoriteSaveRequest(BaseModel):
    name: str = Field(..., min_length=1)
    sql: str = Field(..., min_length=1)
    question: str = ""
    ds_type: str = ""


class FavoriteRenameRequest(BaseModel):
    name: str = Field(..., min_length=1)


@router.get("/favorites")
def favorites_list() -> dict[str, Any]:
    return {"favorites": fav_store.list()}


@router.post("/favorites", status_code=201)
def favorites_save(req: FavoriteSaveRequest) -> dict[str, Any]:
    entry = fav_store.save(req.name, req.sql, req.question, req.ds_type)
    return {"favorite": entry}


@router.patch("/favorites/{fav_id}")
def favorites_rename(fav_id: str, req: FavoriteRenameRequest) -> dict[str, Any]:
    if not fav_store.rename(fav_id, req.name):
        raise HTTPException(status_code=404, detail="unknown favorite")
    return {"renamed": True}


@router.delete("/favorites/{fav_id}")
def favorites_delete(fav_id: str) -> dict[str, Any]:
    if not fav_store.delete(fav_id):
        raise HTTPException(status_code=404, detail="unknown favorite")
    return {"deleted": True}


# ── Feedback ─────────────────────────────────────────────────────────


class FeedbackRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)
    sql: str = Field(..., min_length=1)
    positive: bool


@router.post("/feedback")
def feedback(req: FeedbackRequest) -> dict[str, Any]:
    entry = sessions.get(req.session_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="unknown session")
    agent = entry.agent
    rt = agent.runtime

    ex_store: ExampleStore = getattr(agent, "example_store", None) or ExampleStore()

    if req.positive:
        tables = extract_tables(req.sql)
        ex_store.add(req.question, req.sql, tables, source="feedback")
        fav_store.save(req.question, req.sql, req.question, rt.ds_type)
        rt.logger.log(
            user_query=req.question, generated_sql=req.sql,
            status="feedback_up",
            extra={"source": rt.source, "kind": "feedback"},
        )
    else:
        ex_store.remove_by_question(req.question)
        rt.logger.log(
            user_query=req.question, generated_sql=req.sql,
            status="feedback_down",
            extra={"source": rt.source, "kind": "feedback"},
        )

    return {"ok": True, "positive": req.positive}
