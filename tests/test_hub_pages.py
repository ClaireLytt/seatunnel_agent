# -*- coding: utf-8 -*-
"""Hub pages: landing (`/`), Data Agents (`/data`), AI Platform (`/ai`).

Offline checks over the three HTML builders — no browser, no LLM.
"""

from __future__ import annotations

from seatunnel_agent.ui import (
    _build_ai_hub_html,
    _build_data_hub_html,
    _build_landing_html,
)

# Every route that must stay reachable from the Data Agents grid.
_DATA_ROUTES = [
    "/seatunnel", "/text2sql", "/datacompare", "/dataskew", "/sqlreview",
    "/lineage", "/impact", "/migrate", "/transpile",
    "/pii", "/schemadrift", "/testgen",
    "/conflint", "/dagcheck", "/metricdiff", "/sqlfmt",
]

# Cross-cutting engineering tools live on the landing page.
_ENG_ROUTES = ["/loginspect", "/uitest", "/mcp", "/settings"]

_AI_ROUTES = ["/orchestrator", "/llmeval", "/promptlab", "/llmcost"]

_DEVOPS_ROUTES = ["/secretscan", "/ciinspect", "/depcheck", "/release"]


class TestLanding:
    def test_links_to_both_workspaces(self):
        html = _build_landing_html()
        assert 'href="/data"' in html
        assert 'href="/ai"' in html

    def test_bilingual_attrs(self):
        html = _build_landing_html()
        assert 'data-zh="数据 Agent 工作区"' in html
        assert 'data-zh="AI 平台"' in html
        assert 'id="st-hub-lang"' in html

    def test_health_strip_rendered(self):
        # <!--STATUS--> must be replaced by the health strip, not left raw.
        html = _build_landing_html()
        assert "<!--STATUS-->" not in html
        assert "st-hub-health" in html

    def test_no_data_or_ai_cards_on_landing(self):
        # The two section cards + the engineering tools — no other agent
        # cards. (The health strip may legitimately link to /settings, so
        # match the card markup.)
        html = _build_landing_html()
        for route in _DATA_ROUTES + _AI_ROUTES:
            assert f'class="st-hub-card" href="{route}"' not in html

    def test_devops_workspace_card(self):
        assert 'href="/devops"' in _build_landing_html()

    def test_engineering_tools_on_landing(self):
        html = _build_landing_html()
        for route in _ENG_ROUTES:
            assert f'class="st-hub-card" href="{route}"' in html, route
        assert 'data-zh="工程工具"' in html


class TestDataHub:
    def test_all_agent_cards_present(self):
        html = _build_data_hub_html()
        for route in _DATA_ROUTES:
            assert f'href="{route}"' in html, route

    def test_back_link_and_lang(self):
        html = _build_data_hub_html()
        assert 'class="st-hub-back" href="/"' in html
        assert 'data-zh="← 返回首页"' in html
        assert 'id="st-hub-lang"' in html

    def test_placeholder_card_gone(self):
        assert "st-hub-card-soon" not in _build_data_hub_html()

    def test_grouped_sections_and_filter(self):
        html = _build_data_hub_html()
        # three titled sections (the class also appears once inside the
        # filter's inline JS, hence the attribute-level assertions)
        for zh in ("构建与接入", "SQL 质量与审查", "血缘与治理"):
            assert f'data-zh="{zh}"' in html, zh
        assert 'id="st-hub-filter"' in html
        # every card is inside exactly one section grid
        assert html.count('class="st-hub-grid"') == 3
        # the engineering tools moved to the landing page
        for route in _ENG_ROUTES:
            assert f'href="{route}"' not in html, route


class TestWorkspaceBackButton:
    """STAMP_JS (loaded by every page) injects the ↩ workspace button."""

    def test_mapping_in_stamp_js(self):
        from seatunnel_agent.lang_pref import STAMP_JS
        for route in _AI_ROUTES:
            assert f"'{route}'" in STAMP_JS, route
        assert "'/ai'" in STAMP_JS and "'/data'" in STAMP_JS
        assert "st-ws-btn" in STAMP_JS
        # hub pages must NOT get the button (they have their own back link),
        # nor the engineering tools that live on the landing page itself
        assert "path === '/' || path === '/data' || path === '/ai'" in STAMP_JS
        for route in _ENG_ROUTES:
            assert f"'{route}'" in STAMP_JS, route

    def test_css_present(self):
        from seatunnel_agent.ui import _CUSTOM_CSS
        assert ".st-ws-btn" in _CUSTOM_CSS


class TestDevopsHub:
    def test_four_module_cards(self):
        from seatunnel_agent.ui import _build_devops_hub_html
        html = _build_devops_hub_html()
        for route in _DEVOPS_ROUTES:
            assert f'href="{route}"' in html, route
        assert 'data-zh="DevOps 工作区"' in html
        assert 'class="st-hub-back" href="/"' in html

    def test_stamp_js_maps_devops(self):
        from seatunnel_agent.lang_pref import STAMP_JS
        for route in _DEVOPS_ROUTES:
            assert f"'{route}'" in STAMP_JS, route
        assert "'/devops'" in STAMP_JS


class TestAiHub:
    def test_four_module_cards(self):
        html = _build_ai_hub_html()
        for route in _AI_ROUTES:
            assert f'href="{route}"' in html, route

    def test_bilingual_and_back(self):
        html = _build_ai_hub_html()
        assert 'data-zh="智能编排"' in html
        assert 'data-zh="LLM 评测"' in html
        assert 'data-zh="Prompt 实验室"' in html
        assert 'data-zh="LLM 成本观测"' in html
        assert 'class="st-hub-back" href="/"' in html
