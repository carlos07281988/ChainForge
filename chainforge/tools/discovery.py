# Copyright 2026 ChainForge Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Runtime Tool Discovery — agents discover and register tools at runtime.

Provides:
  - RuntimeToolRegistry: dynamic registry agents can query at runtime
  - Tool capability query: inspect tool capabilities before calling
  - Auto-connect MCP: discover + register MCP server tools

Usage:
    from chainforge.tools.discovery import RuntimeToolRegistry

    registry = RuntimeToolRegistry()
    registry.register(search_tool)
    registry.register(weather_tool, tags=["weather", "info"])

    # Agent queries available tools
    tools = registry.query(capability="web_search")
    tools = registry.query_by_tag("weather")
"""

from __future__ import annotations

from typing import Any

from chainforge.core.tool import Tool, ToolSpec, FunctionTool
from chainforge.logging import get_logger
from chainforge.mcp.registry import MCPRegistry, discover_servers
from chainforge.mcp.client import MCPClient, MCPServer

logger = get_logger("tools.discovery")


class ToolRegistration:
    """A registered tool with metadata."""
    def __init__(self, tool: Tool, tags: list[str] | None = None, capabilities: set[str] | None = None):
        self.tool = tool
        self.tags = tags or []
        self.capabilities = capabilities or set()
        self.created_at = __import__("time").time()

    @property
    def name(self) -> str:
        return self.tool.spec.name

    @property
    def description(self) -> str:
        return self.tool.spec.description


class RuntimeToolRegistry:
    """Dynamic tool registry that agents can query at runtime.

    Supports:
    - Register/unregister tools with tags and capabilities
    - Query by name, tag, capability, or text search
    - Auto-discover MCP tools from the environment
    - Export filtered tool lists for Agent use

    Usage:
        registry = RuntimeToolRegistry()
        registry.register(my_tool, tags=["search"], capabilities={"web_search"})

        # Discover and register MCP tools
        await registry.discover_mcp()

        # Agent queries
        search_tools = registry.query_by_tag("search")
        web_tools = registry.query(capability="web_search")

        # Export for Agent
        agent = Agent(llm=llm, tools=registry.to_tool_list())
    """

    def __init__(self):
        self._tools: dict[str, ToolRegistration] = {}

    # ── Registration ────────────────────────────────────────────────────

    def register(
        self,
        tool: Tool | FunctionTool,
        tags: list[str] | None = None,
        capabilities: set[str] | None = None,
    ) -> str:
        """Register a tool.

        Args:
            tool: The tool to register.
            tags: Search tags (e.g., ["weather", "info"]).
            capabilities: Capability identifiers (e.g., {"web_search", "read"}).

        Returns:
            Tool name.
        """
        name = tool.spec.name
        self._tools[name] = ToolRegistration(
            tool=tool,
            tags=tags or [],
            capabilities=capabilities or set(),
        )
        logger.info(f"Registered tool: {name} (tags={tags}, caps={capabilities})")
        return name

    def unregister(self, name: str) -> bool:
        """Unregister a tool by name."""
        if name in self._tools:
            del self._tools[name]
            logger.info(f"Unregistered tool: {name}")
            return True
        return False

    def register_from_tool_list(self, tools: list[Tool]) -> list[str]:
        """Register multiple tools at once, returning their names."""
        names = []
        for t in tools:
            names.append(self.register(t))
        return names

    # ── Query ───────────────────────────────────────────────────────────

    def list(self) -> list[ToolRegistration]:
        """List all registered tools."""
        return list(self._tools.values())

    def get(self, name: str) -> ToolRegistration | None:
        """Get a tool registration by name."""
        return self._tools.get(name)

    def query(self, capability: str | None = None, tag: str | None = None) -> list[Tool]:
        """Query tools by capability and/or tag."""
        results = []
        for reg in self._tools.values():
            if capability and capability not in reg.capabilities:
                continue
            if tag and tag not in reg.tags:
                continue
            results.append(reg.tool)
        return results

    def query_by_tag(self, tag: str) -> list[Tool]:
        """Query tools by tag."""
        return [reg.tool for reg in self._tools.values() if tag in reg.tags]

    def query_by_capability(self, capability: str) -> list[Tool]:
        """Query tools by capability."""
        return [reg.tool for reg in self._tools.values() if capability in reg.capabilities]

    def search(self, text: str) -> list[Tool]:
        """Search tools by name or description."""
        text_lower = text.lower()
        results = []
        for reg in self._tools.values():
            if text_lower in reg.name.lower() or text_lower in reg.description.lower():
                results.append(reg.tool)
        return results

    # ── MCP Discovery ──────────────────────────────────────────────────

    async def discover_mcp(self, registry: MCPRegistry | None = None) -> int:
        """Discover and register MCP servers.

        Args:
            registry: MCPRegistry instance. Creates default if None.

        Returns:
            Number of newly registered tools.
        """
        from chainforge.mcp.client import MCPClient, MCPServer

        reg = registry or MCPRegistry()
        count = 0

        for server_info in reg.list():
            if not server_info.installed:
                continue

            existing_count = len(self._tools)
            server = MCPServer(
                name=server_info.name,
                command=server_info.command,
                transport=server_info.transport,
                url=server_info.url or "",
            )

            try:
                client = MCPClient()
                await client.connect(server)
                mcp_tools = await client.list_tools()
                await client.disconnect()

                for mcp_tool in mcp_tools:
                    if mcp_tool.spec.name not in self._tools:
                        self.register(
                            mcp_tool,
                            tags=server_info.tags,
                            capabilities={f"mcp:{server_info.name}", f"mcp:{mcp_tool.spec.name}"},
                        )
                        count += 1

                logger.info(f"Discovered {len(mcp_tools)} tools from MCP server '{server_info.name}'")
            except Exception as e:
                logger.warning(f"Failed to connect MCP server '{server_info.name}': {e}")

        return count

    # ── Export ──────────────────────────────────────────────────────────

    def to_tool_list(self, tags: list[str] | None = None, capabilities: set[str] | None = None) -> list[Tool]:
        """Export tools filtered by tags and/or capabilities.

        Args:
            tags: Only include tools with ALL these tags.
            capabilities: Only include tools with ALL these capabilities.

        Returns:
            Filtered list of Tool objects suitable for Agent(tools=...).
        """
        results = list(self._tools.values())

        if tags:
            results = [r for r in results if all(t in r.tags for t in tags)]
        if capabilities:
            results = [r for r in results if all(c in r.capabilities for c in capabilities)]

        return [r.tool for r in results]

    @property
    def count(self) -> int:
        return len(self._tools)

    def summary(self) -> str:
        """Human-readable summary of all registered tools."""
        lines = [f"RuntimeToolRegistry: {self.count} tools", "=" * 35]
        tags_index: dict[str, int] = {}
        cap_index: dict[str, int] = {}

        for reg in self._tools.values():
            for tag in reg.tags:
                tags_index[tag] = tags_index.get(tag, 0) + 1
            for cap in reg.capabilities:
                cap_index[cap] = cap_index.get(cap, 0) + 1

        if tags_index:
            lines.append("Tags:")
            for tag, count in sorted(tags_index.items(), key=lambda x: -x[1]):
                lines.append(f"  {tag}: {count} tools")
        if cap_index:
            lines.append("Capabilities:")
            for cap, count in sorted(cap_index.items(), key=lambda x: -x[1]):
                lines.append(f"  {cap}: {count} tools")
        return "\n".join(lines)
