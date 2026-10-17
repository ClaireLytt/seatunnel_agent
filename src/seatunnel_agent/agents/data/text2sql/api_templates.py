"""SQL templates sub-router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from .templates import SQL_TEMPLATES

router = APIRouter()


@router.get("/templates")
def templates_list() -> dict[str, Any]:
    return {"templates": SQL_TEMPLATES}
