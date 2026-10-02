# -*- coding: utf-8 -*-
"""Run one prompt across several LLM provider profiles.

Profiles are the named snapshots the /settings page stores
(:mod:`seatunnel_agent.settings_store`); each one is turned into a private
:class:`~seatunnel_agent.config.Settings` — the process environment and the
active profile are **never** touched, so an experiment cannot switch the
whole app's provider.  The pseudo-profile ``"(active)"`` runs against the
currently configured LLM.

Every cell is isolated: one provider erroring (bad key, timeout) becomes
that cell's ``error`` instead of killing the matrix.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from ..config import Settings, load_settings
from ..settings_store import load_profile

ACTIVE = "(active)"
_MAX_WORKERS = 4
_DEFAULT_SYSTEM = "You are a helpful assistant."


@dataclass
class CellResult:
    profile: str
    provider: str = ""
    model: str = ""
    reply: str = ""
    thinking: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MatrixResult:
    prompt: str
    system: str
    cells: list[CellResult] = field(default_factory=list)

    @property
    def all_failed(self) -> bool:
        return bool(self.cells) and all(c.error for c in self.cells)


def settings_from_profile(values: dict[str, str]) -> Settings:
    """Map a profile's MANAGED_KEYS env names onto a fresh ``Settings`` —
    no ``os.environ`` mutation (that is the *activate* mechanism, not ours)."""
    def _get(key: str, default: str = "") -> str:
        return str(values.get(key) or default).strip()

    def _num(key: str, default: float, cast: Callable) -> Any:
        raw = _get(key)
        if not raw:
            return cast(default)
        try:
            return cast(float(raw))
        except ValueError:
            raise ValueError(f"profile 的 {key}={raw!r} 不是有效数字")

    return Settings(
        api_key=_get("API_KEY"),
        llm_provider=_get("LLM_PROVIDER", "anthropic").lower(),
        model_name=_get("MODEL_NAME", "claude-opus-5"),
        llm_base_url=_get("LLM_BASE_URL"),
        temperature=_num("TEMPERATURE", 0.0, float),
        max_tokens=_num("MAX_TOKENS", 16000, int),
        llm_timeout=_num("LLM_TIMEOUT", 120, int),
    )


def _resolve_settings(profile: str) -> Settings:
    if profile == ACTIVE:
        return load_settings()
    values = load_profile(profile)
    if not values:
        raise KeyError(f"profile 不存在: {profile}")
    s = settings_from_profile(values)
    if not s.api_key:
        raise ValueError(f"profile {profile} 没有保存 API key")
    return s


def _run_cell(profile: str, prompt: str, system: str,
              client_factory: Callable[[Settings], Any]) -> CellResult:
    cell = CellResult(profile=profile)
    start = time.time()
    try:
        settings = _resolve_settings(profile)
        cell.provider = settings.llm_provider
        cell.model = settings.model_name
        client = client_factory(settings)
        resp = client.chat(system, [{"role": "user", "content": prompt}])
        cell.reply = resp.reply_text or ""
        cell.thinking = resp.thinking_text or ""
        usage = resp.usage or {}
        cell.input_tokens = int(usage.get("input_tokens", 0) or 0)
        cell.output_tokens = int(usage.get("output_tokens", 0) or 0)
    except Exception as exc:  # noqa: BLE001 — isolate the cell
        cell.error = f"{type(exc).__name__}: {exc}"
    cell.latency_ms = int((time.time() - start) * 1000)
    return cell


def run_matrix(prompt: str,
               system: str | None = None,
               profiles: list[str] | None = None,
               parallel: bool = False,
               client_factory: Callable[[Settings], Any] | None = None,
               ) -> MatrixResult:
    """Run *prompt* once per profile; result cells keep the input order."""
    if not (prompt or "").strip():
        raise ValueError("prompt is required")
    system = (system or "").strip() or _DEFAULT_SYSTEM
    profiles = profiles or [ACTIVE]
    if client_factory is None:
        from ..llm import LLMClient
        client_factory = LLMClient

    def job(p: str) -> CellResult:
        return _run_cell(p, prompt, system, client_factory)

    if parallel and len(profiles) > 1:
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
            cells = list(pool.map(job, profiles))  # map preserves order
    else:
        cells = [job(p) for p in profiles]

    result = MatrixResult(prompt=prompt, system=system, cells=cells)
    from .xlog import ExperimentLogger
    ExperimentLogger().log(result)
    return result
