# -*- coding: utf-8 -*-
"""Web-task agent — goal-driven browser loop (snapshot → act → observe)."""

from .engine import WebTaskResult, run_task
from .session import PlaywrightSession

__all__ = ["PlaywrightSession", "WebTaskResult", "run_task"]
