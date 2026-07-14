"""MCP Tool Registry — discover, install, and manage MCP servers.

Provides:
  - A local JSON-based registry of MCP server configurations
  - Built-in list of well-known MCP servers
  - Search, add, remove, install operations
  - Path: ~/.chainforge/mcp_servers.json

Usage:
    from chainforge.mcp.registry import MCPRegistry

    registry = MCPRegistry()
    registry.add_builtin("filesystem")
    servers = registry.list()
    print([s.name for s in servers])
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from chainforge.logging import get_logger

logger = get_logger("mcp.registry")


class MCPServerInfo(BaseModel):
    """MCP server metadata stored in the registry."""

    name: str = Field(description="Server name")
    description: str = Field(default="", description="Server description")
    command: str = Field(default="", description="Shell command to start")
    url: str | None = Field(default=None, description="HTTP URL for remote server")
    transport: str = Field(default="stdio", description="Transport: stdio or sse")
    source: str = Field(default="", description="Install source (npm/github/url)")
    tags: list[str] = Field(default_factory=list, description="Search tags")
    tools: list[str] = Field(default_factory=list, description="Known tool names")
    installed: bool = Field(default=False, description="Whether command is available")


# ── Built-in MCP server definitions ──────────────────────────────────────────

BUILTIN_SERVERS: dict[str, dict[str, Any]] = {
    "filesystem": {
        "name": "filesystem",
        "description": "Filesystem access — read, write, move files",
        "command": "npx -y @modelcontextprotocol/server-filesystem",
        "transport": "stdio",
        "tags": ["files", "system", "io"],
        "tools": ["read_file", "write_file", "list_files", "move_file", "search_files"],
    },
    "github": {
        "name": "github",
        "description": "GitHub API — repos, issues, PRs",
        "command": "npx -y @modelcontextprotocol/server-github",
        "transport": "stdio",
        "tags": ["github", "git", "dev"],
        "tools": ["create_repository", "get_repository", "search_repositories"],
    },
    "sqlite": {
        "name": "sqlite",
        "description": "SQLite database exploration and queries",
        "command": "npx -y @modelcontextprotocol/server-sqlite",
        "transport": "stdio",
        "tags": ["database", "sql", "data"],
        "tools": ["query", "list_tables", "describe_table"],
    },
    "web_search": {
        "name": "web_search",
        "description": "Web search via Brave Search API",
        "command": "npx -y @anthropic/mcp-web-search",
        "transport": "stdio",
        "tags": ["web", "search", "internet"],
        "tools": ["web_search"],
    },
    "playwright": {
        "name": "playwright",
        "description": "Browser automation — navigation, screenshots, data extraction",
        "command": "npx -y @anthropic/mcp-playwright",
        "transport": "stdio",
        "tags": ["browser", "web", "automation"],
        "tools": ["navigate", "screenshot", "click", "type", "extract_text"],
    },
    "memory": {
        "name": "memory",
        "description": "Persistent memory — store and retrieve knowledge",
        "command": "npx -y @modelcontextprotocol/server-memory",
        "transport": "stdio",
        "tags": ["memory", "knowledge", "persistence"],
        "tools": ["remember", "recall", "forget"],
    },
    "slack": {
        "name": "slack",
        "description": "Slack messaging — channels, messages, users",
        "command": "npx -y @modelcontextprotocol/server-slack",
        "transport": "stdio",
        "tags": ["slack", "communication", "messaging"],
        "tools": ["send_message", "list_channels", "get_history"],
    },
    "fetch": {
        "name": "fetch",
        "description": "Fetch web pages and convert to markdown",
        "command": "uvx mcp-server-fetch",
        "transport": "stdio",
        "tags": ["web", "fetch", "http"],
        "tools": ["fetch", "fetch_markdown"],
    },
}


def get_builtin_names() -> list[str]:
    """Return list of built-in MCP server names."""
    return list(BUILTIN_SERVERS.keys())


def get_builtin(name: str) -> MCPServerInfo | None:
    """Get a built-in MCP server definition by name."""
    data = BUILTIN_SERVERS.get(name)
    if data:
        return MCPServerInfo(**data)
    return None


# ── Registry ─────────────────────────────────────────────────────────────────


class MCPRegistry:
    """Local registry of MCP server configurations.

    Stores servers in ~/.chainforge/mcp_servers.json.

    Args:
        path: Custom path for the registry file.
              Defaults to ~/.chainforge/mcp_servers.json.
    """

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else Path.home() / ".chainforge" / "mcp_servers.json"
        self._servers: dict[str, MCPServerInfo] = {}
        self._load()

    # ── Persistence ────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Load registry from disk."""
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                for item in data:
                    server = MCPServerInfo(**item)
                    self._servers[server.name] = server
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to load MCP registry: {e}")

    def save(self) -> None:
        """Save registry to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = [s.model_dump(mode="json") for s in self._servers.values()]
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        logger.debug(f"MCP registry saved ({len(data)} servers)")

    # ── Query ──────────────────────────────────────────────────────────────

    def list(self) -> list[MCPServerInfo]:
        """List all registered MCP servers."""
        return list(self._servers.values())

    def get(self, name: str) -> MCPServerInfo | None:
        """Get a server by name."""
        return self._servers.get(name)

    def search(self, query: str) -> list[MCPServerInfo]:
        """Search servers by name, description, or tags."""
        q = query.lower()
        results = []
        for server in self._servers.values():
            if (q in server.name.lower()
                    or q in server.description.lower()
                    or any(q in tag.lower() for tag in server.tags)):
                results.append(server)
        return results

    # ── Management ─────────────────────────────────────────────────────────

    def add(self, server: MCPServerInfo) -> None:
        """Add a server to the registry."""
        self._servers[server.name] = server
        self.save()
        logger.info(f"Added MCP server: {server.name}")

    def remove(self, name: str) -> bool:
        """Remove a server from the registry.

        Returns:
            True if removed, False if not found.
        """
        if name in self._servers:
            del self._servers[name]
            self.save()
            logger.info(f"Removed MCP server: {name}")
            return True
        return False

    def add_builtin(self, name: str) -> MCPServerInfo | None:
        """Add a built-in MCP server to the registry.

        Args:
            name: Built-in server name.

        Returns:
            The server info if found, None otherwise.
        """
        data = BUILTIN_SERVERS.get(name)
        if data is None:
            logger.warning(f"Unknown built-in MCP server: {name}")
            return None

        server = MCPServerInfo(**data)
        server.installed = _check_command_available(server.command)
        self.add(server)
        return server

    def add_custom(
        self,
        name: str,
        command: str,
        *,
        description: str = "",
        transport: str = "stdio",
        tags: list[str] | None = None,
    ) -> MCPServerInfo:
        """Add a custom MCP server.

        Args:
            name: Server name.
            command: Shell command to start the server.
            description: Human-readable description.
            transport: "stdio" or "sse".
            tags: Search tags.

        Returns:
            The created server info.
        """
        server = MCPServerInfo(
            name=name,
            description=description,
            command=command,
            transport=transport,
            source="custom",
            tags=tags or [],
            installed=_check_command_available(command),
        )
        self.add(server)
        return server

    @property
    def count(self) -> int:
        return len(self._servers)

    def stats(self) -> dict[str, Any]:
        return {
            "total": self.count,
            "installed": sum(1 for s in self._servers.values() if s.installed),
            "path": str(self.path),
        }


def _check_command_available(command: str) -> bool:
    """Check if an MCP server command is available on the system.

    Extracts the first word (npx, uvx, etc.) and checks if it exists.
    """
    if not command:
        return False
    first_word = command.split()[0]
    return shutil.which(first_word) is not None
