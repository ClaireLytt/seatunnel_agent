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
            if not mf.external:
                assert callable(resolve(mf.render)), mf.name
            if mf.api:
                router = resolve(mf.api)
                assert hasattr(router, "routes"), mf.name

    def test_resolve_bad_target(self):
        with pytest.raises((ModuleNotFoundError, AttributeError)):
            resolve("seatunnel_agent.nope:thing")


# every hard-coded data-agent route in hub/ui.py must be manifest-covered
_DATA_ROUTES = {
    "/seatunnel", "/text2sql",
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
        assert no_card == {"/loginspect", "/mcp"}


# data agents whose REST routers used to be a hand-maintained tuple in
# launch_app — they must now declare api= so the manifest loop mounts them.
# sql_review is not listed: its router is mounted unconditionally by the
# launcher (the React page depends on it), same as uitest. config_lint,
# sql_fmt, sql_transpile and data_skew moved off the list for the same
# reason when their pages went React.
_DATA_API_NAMES = {
    "text2sql", "data_lineage",
    "pii_scan", "log_inspect", "schema_drift", "sql_testgen",
    "dag_check", "metric_diff",
}


class TestDataApiRouters:
    def test_router_bearing_agents_declare_api(self):
        by_name = {m.name: m for m in workspace_manifests("data")}
        missing = [n for n in _DATA_API_NAMES if not by_name[n].api]
        assert not missing, missing


class TestExternalManifest:
    def test_external_entry_keeps_card_but_no_render(self):
        # /text2sql is served by the React static mount (#67): its manifest
        # entry is external — card on the hub, no Gradio route/render
        from seatunnel_agent.hub.registry import discover
        by_route = {m.route: m for m in discover()}
        main = by_route["/text2sql"]
        assert main.external is True
        assert main.card is True
        assert "/text2sql-legacy" not in by_route  # legacy retired

class TestExternalMounting:
    def test_external_apps_follow_dist_convention(self):
        from pathlib import Path

        from seatunnel_agent.hub.registry import frontend_dist
        ext = {m.name: m for m in discover() if m.external}
        # every rebuilt React app registers an external manifest
        assert {"uitest", "text2sql"} <= set(ext)
        assert frontend_dist(ext["text2sql"]) == Path("frontend") / "text2sql" / "dist"
        assert frontend_dist(ext["uitest"]) == Path("frontend") / "uitest" / "dist"
        # hint page may link a legacy route when one exists
        assert ext["text2sql"].legacy is None or ext["text2sql"].legacy == "/text2sql-legacy"  # may still carry the hint
        assert ext["uitest"].legacy is None

    def test_external_workspace_dir_matches_manifest_name(self):
        # The hub mounts frontend/<manifest.name>/dist. A workspace created
        # under any other directory name (e.g. the route name) silently never
        # mounts and the page serves the "not built" hint forever — this bit
        # /datacompare (frontend/datacompare vs name=data_comparison, fixed in
        # 615482a). Guard: the workspace directory must exist for every
        # external manifest.
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        for mf in discover():
            if not mf.external:
                continue
            ws = root / "frontend" / mf.name
            assert (ws / "package.json").is_file(), (
                f"external manifest {mf.name!r} has no frontend/{mf.name}/ "
                f"workspace — directory name must equal manifest.name"
            )


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
