"""Plugin registry: discovery, validation, resolution, card rendering."""

from __future__ import annotations

import pytest

from seatunnel_agent.hub.registry import (
    AgentManifest,
    card_html,
    discover,
    resolve,
    workspace_manifests,
)

EXPECTED = {
    "orchestrator", "llm_eval", "prompt_lab", "llm_cost",
    "secret_scan", "ci_inspect", "dep_check", "release_notes",
}


class TestDiscovery:
    def test_all_plugins_found(self):
        names = {m.name for m in discover()}
        assert EXPECTED <= names

    def test_routes_and_names_unique(self):
        ms = discover()
        routes = [m.route for m in ms]
        names = [m.name for m in ms]
        assert len(routes) == len(set(routes))
        assert len(names) == len(set(names))

    def test_workspace_split(self):
        ai = {m.name for m in workspace_manifests("ai")}
        devops = {m.name for m in workspace_manifests("devops")}
        assert {"orchestrator", "llm_eval", "prompt_lab", "llm_cost"} <= ai
        assert {"secret_scan", "ci_inspect", "dep_check",
                "release_notes"} <= devops
        assert not ai & devops

    def test_order_respected(self):
        devops = [m.name for m in workspace_manifests("devops")]
        assert devops.index("secret_scan") < devops.index("release_notes")


class TestResolution:
    def test_every_render_and_api_resolves(self):
        for mf in discover():
            assert callable(resolve(mf.render)), mf.name
            if mf.api:
                router = resolve(mf.api)
                assert hasattr(router, "routes"), mf.name

    def test_resolve_bad_target(self):
        with pytest.raises((ModuleNotFoundError, AttributeError)):
            resolve("seatunnel_agent.nope:thing")


class TestCardHtml:
    def test_markup_shape_and_escaping(self):
        mf = AgentManifest(
            name="x", workspace="ai", route="/x", page_title="X",
            logo="X", color="#000", title_en="A & B", title_zh="甲",
            desc_en="d", desc_zh="述", render="m:f")
        html = card_html(mf)
        assert 'href="/x"' in html
        assert "A &amp; B" in html           # escaped
        assert 'data-zh="甲"' in html
        # rich card: colored logo tile + colored bilingual "Enter →" row
        assert 'style="background:#000;"' in html
        assert ('<div class="st-hub-enter" style="color:#000;" '
                'data-en="Enter →" data-zh="进入 →">Enter →</div>') in html
        # unknown route → glyph fallback inside the colored logo tile
        assert ">X</div>" in html

    def test_group_field_optional(self):
        mf = AgentManifest(
            name="x", workspace="data", route="/x", page_title="X",
            logo="X", color="#000", title_en="t", title_zh="题",
            desc_en="d", desc_zh="述", render="m:f", group="quality")
        assert mf.group == "quality"
        base = AgentManifest(
            name="y", workspace="ai", route="/y", page_title="Y",
            logo="Y", color="#000", title_en="t", title_zh="题",
            desc_en="d", desc_zh="述", render="m:f")
        assert base.group is None
