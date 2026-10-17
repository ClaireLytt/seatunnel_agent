"""Boards CRUD + pin + render sub-router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .api_shared import sessions
from .boards import BoardStore, render_board

router = APIRouter()

_board_store = BoardStore()


@router.get("/boards")
def boards_list() -> dict[str, Any]:
    return {"boards": _board_store.list()}


class BoardCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)


@router.post("/boards", status_code=201)
def boards_create(req: BoardCreateRequest) -> dict[str, Any]:
    try:
        board = _board_store.create(req.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"board": board}


@router.delete("/boards/{board_id}")
def boards_delete(board_id: str) -> dict[str, Any]:
    if not _board_store.delete(board_id):
        raise HTTPException(status_code=404, detail="unknown board")
    return {"deleted": True}


class PinRequest(BaseModel):
    title: str = ""
    sql: str = Field(..., min_length=1)
    ds_type: str = ""


@router.post("/boards/{board_id}/pin")
def boards_pin(board_id: str, req: PinRequest) -> dict[str, Any]:
    try:
        item = _board_store.pin(board_id, req.title, req.sql, req.ds_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"item": item}


@router.get("/boards/{board_id}/render")
def boards_render(board_id: str, session_id: str) -> dict[str, Any]:
    board = _board_store.get(board_id)
    if board is None:
        raise HTTPException(status_code=404, detail="unknown board")
    entry = sessions.get(session_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="unknown session")
    agent = entry.agent
    rt = agent.runtime
    results = render_board(
        board, rt.executor, rt.store, ds_type=rt.ds_type,
    )
    return {"board_id": board_id, "name": board.get("name", ""), "results": results}
