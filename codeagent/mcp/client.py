from __future__ import annotations

import re
from typing import Any, Callable


class MCPClient:
    def __init__(self, name: str) -> None:
        self.name = name
        self.tools: list[dict[str, Any]] = []
        self._handlers: dict[str, Callable[..., str]] = {}

    def register(self, tool_defs: list[dict[str, Any]], handlers: dict[str, Callable[..., str]]) -> None:
        self.tools = tool_defs
        self._handlers = handlers

    def call_tool(self, tool_name: str, args: dict[str, Any]) -> str:
        handler = self._handlers.get(tool_name)
        if not handler:
            return f"MCP error: unknown tool '{tool_name}'"
        try:
            return str(handler(**args))
        except Exception as exc:
            return f"MCP error: {exc}"


_DISALLOWED_CHARS = re.compile(r"[^a-zA-Z0-9_-]")


def normalize_mcp_name(name: str) -> str:
    return _DISALLOWED_CHARS.sub("_", name)


def _mock_docs() -> MCPClient:
    client = MCPClient("docs")
    client.register(
        [
            {"name": "search", "description": "Search documentation. (readOnly)", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
            {"name": "get_version", "description": "Get API version. (readOnly)", "inputSchema": {"type": "object", "properties": {}, "required": []}},
        ],
        {
            "search": lambda query: f"[docs] Found 3 results for '{query}'",
            "get_version": lambda: "[docs] API v2.1.0",
        },
    )
    return client


def _mock_deploy() -> MCPClient:
    client = MCPClient("deploy")
    client.register(
        [
            {"name": "trigger", "description": "Trigger a deployment. (destructive)", "inputSchema": {"type": "object", "properties": {"service": {"type": "string"}}, "required": ["service"]}},
            {"name": "status", "description": "Check deployment status. (readOnly)", "inputSchema": {"type": "object", "properties": {"service": {"type": "string"}}, "required": ["service"]}},
        ],
        {
            "trigger": lambda service: f"[deploy] Triggered: {service}",
            "status": lambda service: f"[deploy] {service}: running (v1.4.2)",
        },
    )
    return client


class MCPRegistry:
    def __init__(self) -> None:
        self.clients: dict[str, MCPClient] = {}
        self.factories: dict[str, Callable[[], MCPClient]] = {
            "docs": _mock_docs,
            "deploy": _mock_deploy,
        }

    def connect(self, name: str) -> str:
        if name in self.clients:
            return f"MCP server '{name}' already connected"
        factory = self.factories.get(name)
        if not factory:
            available = ", ".join(self.factories.keys())
            return f"Unknown server '{name}'. Available: {available}"
        client = factory()
        self.clients[name] = client
        tool_names = [tool["name"] for tool in client.tools]
        return f"Connected to MCP server '{name}'. Discovered {len(client.tools)} tools: {', '.join(tool_names)}"

    def connected_names(self) -> list[str]:
        return list(self.clients.keys())
