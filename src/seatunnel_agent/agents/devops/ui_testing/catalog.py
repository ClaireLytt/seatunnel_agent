"""Suite / agent-picker catalog shared by the API and CLI layers."""

from __future__ import annotations

SUITES = ["smoke", "full", "sqlite", "hive", "slow"]

# Agent picker: route prefixes -> every automated case on those pages.
AGENT_ROUTES: dict[str, tuple[str, ...]] = {
    "all": (),
    "datacompare": ("/datacompare",),
    "lineage": ("/lineage",),
    "text2sql": ("/text2sql", "/history", "/favorites", "/schema-browser"),
    "transpile": ("/transpile",),
    "impact": ("/impact",),
    "migrate": ("/migrate",),
    "dataskew": ("/dataskew",),
    "mcp": ("/mcp",),
    "settings": ("/settings",),
}

AGENT_LABELS = {
    "en": {"all": "All agents", "datacompare": "Data Comparison",
           "lineage": "Data Lineage",
           "text2sql": "Text2SQL & aux pages",
           "transpile": "SQL Dialect Translation",
           "impact": "Change Impact Analysis",
           "migrate": "DataX/Sqoop Migration",
           "dataskew": "Data Skew Analyzer",
           "mcp": "MCP Toolbox",
           "settings": "Settings"},
    "zh": {"all": "全部 Agent", "datacompare": "数据对比",
           "lineage": "数据血缘",
           "text2sql": "Text2SQL 与辅助页",
           "transpile": "SQL 方言翻译",
           "impact": "变更影响分析",
           "migrate": "配置迁移",
           "dataskew": "数据倾斜分析",
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
