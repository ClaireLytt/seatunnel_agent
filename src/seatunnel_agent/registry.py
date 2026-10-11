# -*- coding: utf-8 -*-
"""Plugin registry — drop-in agent packages, auto-discovered.

A package under ``seatunnel_agent`` becomes a platform plugin by shipping a
``manifest.py`` with a module-level ``MANIFEST = AgentManifest(...)``.
Discovery wires it everywhere at once:

* hub card on its workspace page (``/ai`` / ``/devops``),
* Gradio route (``render`` is imported lazily when the UI is built),
* REST router under ``seatunnel-agent ui --api`` (``api``).

Adding a capability used to mean editing ui.py in three places; now it
means dropping a package with a manifest.  Manifest modules must stay
import-light (strings only — no heavy imports at module level).
"""

from __future__ import annotations

import html as _html
import importlib
import pkgutil
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

WORKSPACES = ("data", "ai", "devops")


@dataclass(frozen=True)
class AgentManifest:
    name: str            # unique slug, e.g. "secret_scan"
    workspace: str       # one of WORKSPACES
    route: str           # "/secretscan"
    page_title: str      # Gradio route title, e.g. "Secret Scan"
    logo: str            # hub-card logo glyph, e.g. "🔑"
    color: str           # hub-card accent, e.g. "#dc2626"
    title_en: str
    title_zh: str
    desc_en: str
    desc_zh: str
    render: str          # "seatunnel_agent.secret_scan_ui:render_secret_scan_page"
    api: str | None = None   # "seatunnel_agent.secret_scan.api:router"
    order: int = 100     # card order within the workspace


def resolve(target: str) -> Any:
    """``"pkg.module:attr"`` → the attribute (imported on demand)."""
    module_name, _, attr = target.partition(":")
    return getattr(importlib.import_module(module_name), attr)


def discover() -> list[AgentManifest]:
    """Every ``seatunnel_agent.<pkg>.manifest.MANIFEST``, validated."""
    import seatunnel_agent as root
    found: list[AgentManifest] = []
    for info in pkgutil.iter_modules(root.__path__):
        if not info.ispkg:
            continue
        mod_name = f"seatunnel_agent.{info.name}.manifest"
        try:
            mod = importlib.import_module(mod_name)
        except ModuleNotFoundError as exc:
            if exc.name == mod_name:
                continue  # package without a manifest — not a plugin
            raise
        mf = getattr(mod, "MANIFEST", None)
        if not isinstance(mf, AgentManifest):
            raise TypeError(f"{mod_name} 必须定义 MANIFEST = AgentManifest(...)")
        if mf.workspace not in WORKSPACES:
            raise ValueError(f"{mod_name}: workspace 必须是 {WORKSPACES}")
        found.append(mf)
    routes = [m.route for m in found]
    dup = {r for r in routes if routes.count(r) > 1}
    if dup:
        raise ValueError(f"manifest 路由冲突: {sorted(dup)}")
    return sorted(found, key=lambda m: (m.workspace, m.order, m.name))


def workspace_manifests(workspace: str) -> list[AgentManifest]:
    return [m for m in discover() if m.workspace == workspace]


_ICON_DIR = Path(__file__).parent / "static" / "icons"


@lru_cache(maxsize=None)
def _icon_svg(slug: str) -> str | None:
    """Vendored Ant Design outlined SVG for a route slug, or None."""
    path = _ICON_DIR / f"{slug}.svg"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def logo_html(route: str, fallback: str = "") -> str:
    """Hub-card icon tile: a single-color antd line icon keyed by route;
    falls back to a two-letter monogram when no SVG is vendored."""
    svg = _icon_svg(route.strip("/"))
    glyph = svg if svg else _html.escape(fallback[:2].upper() or "·")
    return f'<div class="st-hub-logo">{glyph}</div>'


def card_html(mf: AgentManifest) -> str:
    """The standard hub card markup (bilingual via data-en/data-zh)."""
    e = _html.escape
    return (
        f'    <a class="st-hub-card" href="{mf.route}">\n'
        f'      {logo_html(mf.route, mf.logo)}\n'
        f'      <div class="st-hub-card-title" data-en="{e(mf.title_en)}" '
        f'data-zh="{e(mf.title_zh)}">{e(mf.title_en)}</div>\n'
        f'      <div class="st-hub-card-desc" data-en="{e(mf.desc_en)}" '
        f'data-zh="{e(mf.desc_zh)}">{e(mf.desc_en)}</div>\n'
        f'    </a>')
