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
    "/lineage", "/impact", "/migrate", "/transpile", "/uitest", "/mcp",
    "/settings", "/pii", "/loginspect", "/schemadrift", "/testgen",
    "/conflint", "/dagcheck", "/metricdiff", "/sqlfmt",
]

_AI_ROUTES = ["/orchestrator", "/llmeval", "/promptlab", "/llmcost"]


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

    def test_no_agent_cards_on_landing(self):
        # Only the two section cards — no per-agent cards. (The health strip
        # may legitimately link to /settings, so match the card markup.)
        html = _build_landing_html()
        for route in _DATA_ROUTES + _AI_ROUTES:
            assert f'class="st-hub-card" href="{route}"' not in html


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
