# -*- coding: utf-8 -*-
"""GitHub bot — PR webhook → secret scan + static SQL review as a comment."""

from .core import BOT_MARKER, BotFinding, PatchFile, parse_patch, review_patch
from .server import create_bot_app, verify_signature

__all__ = [
    "BOT_MARKER",
    "BotFinding",
    "PatchFile",
    "create_bot_app",
    "parse_patch",
    "review_patch",
    "verify_signature",
]
