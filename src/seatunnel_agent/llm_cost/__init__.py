# -*- coding: utf-8 -*-
"""LLM cost observability — price the cross-agent usage log.

Deterministic: reads ``logs/llm_usage.jsonl`` (written by every
``LLMClient.chat`` call), prices it against an approximate, overridable
catalog, and reports per-model / per-day / per-agent spend with anomaly
flags.  No database, no LLM.
"""

from .aggregate import check_budget, summarize_cost
from .pricing import (
    PriceEntry,
    builtin_prices,
    cost_usd,
    load_override,
    merged_prices,
    override_path,
    price_for,
)
from .report import render_markdown

__all__ = [
    "PriceEntry",
    "builtin_prices",
    "check_budget",
    "cost_usd",
    "load_override",
    "merged_prices",
    "override_path",
    "price_for",
    "render_markdown",
    "summarize_cost",
]
