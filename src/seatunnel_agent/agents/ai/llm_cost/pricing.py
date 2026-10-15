# -*- coding: utf-8 -*-
"""Model pricing catalog — USD per 1M tokens, longest-prefix matched.

The built-in table covers the providers the platform ships adapters for.
List prices change and vary by region/tier, so the catalog is explicitly
**approximate**: every number can be overridden (and new models added) via a
YAML file at ``SEATUNNEL_PRICING_PATH`` or ``~/.seatunnel-agent/pricing.yaml``:

    prices:
      - model: deepseek-chat      # prefix, longest match wins
        input: 0.27               # USD per 1M input tokens
        output: 1.10              # USD per 1M output tokens

Unknown models are never guessed — they land in the "unpriced" bucket so the
report can say exactly which spend is not counted.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PriceEntry:
    prefix: str          # matched against model.lower().startswith(...)
    input_usd: float     # USD per 1M input tokens
    output_usd: float    # USD per 1M output tokens
    source: str = "builtin"   # "builtin" | "override"


# (prefix, input $/MTok, output $/MTok) — approximate list prices.
_BUILTIN: list[tuple[str, float, float]] = [
    # Anthropic
    ("claude-opus-5", 5.0, 25.0),
    ("claude-sonnet-5", 3.0, 15.0),
    ("claude-opus-4-5", 5.0, 25.0),
    ("claude-opus-4-1", 15.0, 75.0),
    ("claude-opus-4", 15.0, 75.0),
    ("claude-sonnet-4", 3.0, 15.0),
    ("claude-haiku-4-5", 1.0, 5.0),
    ("claude-3-7-sonnet", 3.0, 15.0),
    ("claude-3-5-sonnet", 3.0, 15.0),
    ("claude-3-5-haiku", 0.80, 4.0),
    # OpenAI
    ("gpt-4o-mini", 0.15, 0.60),
    ("gpt-4o", 2.50, 10.0),
    ("gpt-4.1-mini", 0.40, 1.60),
    ("gpt-4.1-nano", 0.10, 0.40),
    ("gpt-4.1", 2.0, 8.0),
    # DeepSeek
    ("deepseek-chat", 0.27, 1.10),
    ("deepseek-reasoner", 0.55, 2.19),
    # Moonshot / Kimi
    ("kimi-k2", 0.60, 2.50),
    ("moonshot-v1", 1.70, 1.70),
    # Alibaba Qwen
    ("qwen-max", 1.60, 6.40),
    ("qwen-plus", 0.40, 1.20),
    ("qwen-turbo", 0.05, 0.20),
    # Zhipu GLM
    ("glm-4-plus", 0.70, 0.70),
    ("glm-4-flash", 0.0, 0.0),
    ("glm-4", 0.70, 0.70),
]


def override_path() -> Path:
    env = os.getenv("SEATUNNEL_PRICING_PATH")
    if env:
        return Path(env)
    return Path.home() / ".seatunnel-agent" / "pricing.yaml"


def builtin_prices() -> list[PriceEntry]:
    return [PriceEntry(p, i, o) for p, i, o in _BUILTIN]


def load_override(path: str | Path | None = None) -> list[PriceEntry]:
    """Read the user's pricing YAML; missing file → []. Raises ``ValueError``
    with a readable message on a malformed file (silent misparse would mean
    silently wrong cost numbers)."""
    p = Path(path) if path else override_path()
    if not p.is_file():
        return []
    try:
        import yaml
    except ImportError:  # pragma: no cover - pyyaml ships with [all]/[dev]
        raise ValueError("价格覆盖文件需要 pyyaml: pip install pyyaml")
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"无法读取价格文件 {p}: {exc}")
    items = raw.get("prices") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        raise ValueError(f"{p}: 期望顶层为 prices: [...] 列表")
    entries: list[PriceEntry] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict) or not item.get("model"):
            raise ValueError(f"{p}: prices[{i}] 缺少 model 字段")
        try:
            entries.append(PriceEntry(
                prefix=str(item["model"]).strip().lower(),
                input_usd=float(item.get("input", 0) or 0),
                output_usd=float(item.get("output", 0) or 0),
                source="override",
            ))
        except (TypeError, ValueError):
            raise ValueError(f"{p}: prices[{i}] 的 input/output 必须是数字")
    return entries


def merged_prices(override: str | Path | None = None) -> list[PriceEntry]:
    """Override entries first so they win prefix-length ties."""
    return load_override(override) + builtin_prices()


def price_for(model: str,
              prices: list[PriceEntry] | None = None) -> PriceEntry | None:
    """Longest-prefix match, case-insensitive; override beats builtin on a
    tie (override entries come first and the sort is stable)."""
    if not model:
        return None
    m = model.strip().lower()
    candidates = [e for e in (prices if prices is not None else merged_prices())
                  if m.startswith(e.prefix)]
    if not candidates:
        return None
    return max(candidates, key=lambda e: len(e.prefix))


def cost_usd(model: str, input_tokens: int, output_tokens: int,
             prices: list[PriceEntry] | None = None) -> float | None:
    """Cost of one call in USD, or ``None`` when the model is unpriced."""
    entry = price_for(model, prices)
    if entry is None:
        return None
    return (input_tokens * entry.input_usd
            + output_tokens * entry.output_usd) / 1_000_000
