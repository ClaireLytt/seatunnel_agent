"""Suite / agent-picker catalog shared by the API and CLI layers."""

from __future__ import annotations

SUITES = ["smoke", "full", "sqlite", "hive", "slow"]

# Agent picker: route prefixes -> every automated case on those pages.
AGENT_ROUTES: dict[str, tuple[str, ...]] = {
    "all": (),
    "lineage": ("/lineage",),
    "text2sql": ("/text2sql", "/history", "/favorites", "/schema-browser"),
    "impact": ("/impact",),
    "mcp": ("/mcp",),
    "settings": ("/settings",),
}

AGENT_LABELS = {
    "en": {"all": "All agents",
           "lineage": "Data Lineage",
           "text2sql": "Text2SQL & aux pages",
           "impact": "Change Impact Analysis",
           "mcp": "MCP Toolbox",
           "settings": "Settings"},
    "zh": {"all": "全部 Agent",
           "lineage": "数据血缘",
           "text2sql": "Text2SQL 与辅助页",
           "impact": "变更影响分析",
           "mcp": "MCP 工具箱",
           "settings": "设置"},
}


def agent_case_ids(agent: str) -> list[str]:
    """Every automated case on the given agent's pages."""
    routes = AGENT_ROUTES.get(agent) or ()
    if not routes:
        return []
    from .loader import load_cases
    return [c.id for c in load_cases()
            if "manual" not in c.tags and c.page.startswith(routes)]
