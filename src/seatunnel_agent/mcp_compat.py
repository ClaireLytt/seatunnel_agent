# -*- coding: utf-8 -*-
"""mcp SDK version shim.

mcp 2.x renamed ``FastMCP`` to ``MCPServer`` (same ``tool()`` / ``run()``
surface for our usage). Every MCP server in this package resolves the
class through here so both SDK generations work.
"""

from __future__ import annotations


def fastmcp_class():
    """The FastMCP/MCPServer class, whichever the installed SDK provides."""
    try:
        from mcp.server.fastmcp import FastMCP  # mcp 1.x
        return FastMCP
    except (ImportError, ModuleNotFoundError):
        pass
    try:
        from mcp.server.mcpserver import MCPServer  # mcp 2.x rename
        return MCPServer
    except (ImportError, ModuleNotFoundError) as exc:
        raise RuntimeError(
            "未安装 mcp 依赖，请先执行: pip install 'seatunnel-agent[mcp]'"
        ) from exc
