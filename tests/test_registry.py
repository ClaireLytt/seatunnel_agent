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


# every hard-coded data-agent route in hub/ui.py must be manifest-covered
_DATA_ROUTES = {
    "/seatunnel", "/text2sql", "/history", "/favorites", "/schema-browser",
    "/datacompare", "/sqlreview", "/lineage", "/transpile", "/impact",
    "/migrate", "/dataskew", "/pii", "/loginspect", "/schemadrift",
    "/testgen", "/conflint", "/dagcheck", "/metricdiff", "/sqlfmt", "/mcp",
}


class TestDataCoverage:
    def test_every_data_route_has_a_manifest(self):
        covered = {m.route for m in workspace_manifests("data")}
        assert _DATA_ROUTES <= covered, sorted(_DATA_ROUTES - covered)

    def test_data_cards_carry_group_and_color(self):
        for m in workspace_manifests("data"):
            if m.card:
                assert m.group, m.name
                assert m.color.startswith("#"), m.name

    def test_cardless_pages_marked(self):
        no_card = {m.route for m in workspace_manifests("data")
                   if not m.card}
        # text2sql aux pages + landing engineering tools keep no /data card
        assert no_card == {"/history", "/favorites", "/schema-browser",
                           "/loginspect", "/mcp"}


# data agents whose REST routers used to be a hand-maintained tuple in
# launch_app — they must now declare api= so the manifest loop mounts them
_DATA_API_NAMES = {
    "text2sql", "sql_review", "data_lineage", "sql_transpile", "data_skew",
    "pii_scan", "log_inspect", "schema_drift", "sql_testgen", "config_lint",
    "dag_check", "metric_diff", "sql_fmt",
}


class TestDataApiRouters:
    def test_router_bearing_agents_declare_api(self):
        by_name = {m.name: m for m in workspace_manifests("data")}
        missing = [n for n in _DATA_API_NAMES if not by_name[n].api]
        assert not missing, missing


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
