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
"""MCP Tool Registry — discover, install, and manage MCP servers.

Provides:
  - A local JSON-based registry of MCP server configurations
  - Built-in list of well-known MCP servers
  - Auto-discovery via environment variables and config files
  - Search, add, remove, install operations
  - Path: ~/.chainforge/mcp_servers.json
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from chainforge.logging import get_logger

logger = get_logger("mcp.registry")

# Key used for auto-discovery via environment
MCP_SERVERS_ENV_VAR = "CHAINFORGE_MCP_SERVERS"
MCP_CONFIG_FILE = ".chainforge-mcp.json"


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
    return list(BUILTIN_SERVERS.keys())


def get_builtin(name: str) -> MCPServerInfo | None:
    data = BUILTIN_SERVERS.get(name)
    if data:
        return MCPServerInfo(**data)
    return None


# ── Auto-discovery ────────────────────────────────────────────────────────────


def discover_servers(
    paths: list[str | Path] | None = None,
) -> list[MCPServerInfo]:
    """Discover MCP servers from environment variables and config files.

    Scans, in order:
    1. CHAINFORGE_MCP_SERVERS env var (JSON string or file path)
    2. .chainforge-mcp.json in current directory
    3. ~/.chainforge/mcp_servers.json
    4. Additional paths provided via argument

    Returns:
        List of discovered MCPServerInfo objects.
    """
    discovered: dict[str, MCPServerInfo] = {}

    # 1. Environment variable
    env_val = os.environ.get(MCP_SERVERS_ENV_VAR)
    if env_val:
        try:
            # Could be a JSON string or a file path
            if env_val.endswith(".json") and os.path.isfile(env_val):
                data = json.loads(Path(env_val).read_text())
            else:
                data = json.loads(env_val)

            servers = _parse_server_list(data)
            for s in servers:
                discovered[s.name] = s
            logger.info(f"Discovered {len(servers)} MCP servers from ${MCP_SERVERS_ENV_VAR}")
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse ${MCP_SERVERS_ENV_VAR}: {e}")

    # 2. Local config file
    config_file = Path.cwd() / MCP_CONFIG_FILE
    if config_file.exists():
        try:
            data = json.loads(config_file.read_text())
            servers = _parse_server_list(data)
            for s in servers:
                discovered[s.name] = s
            logger.info(f"Discovered {len(servers)} MCP servers from {config_file}")
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse {config_file}: {e}")

    # 3. Default registry path
    default_registry = Path.home() / ".chainforge" / "mcp_servers.json"
    if default_registry.exists():
        try:
            data = json.loads(default_registry.read_text())
            servers = _parse_server_list(data)
            for s in servers:
                discovered[s.name] = s
            logger.info(f"Discovered {len(servers)} MCP servers from {default_registry}")
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse {default_registry}: {e}")

    # 4. Additional paths
    if paths:
        for p in paths:
            path = Path(p)
            if path.exists():
                try:
                    data = json.loads(path.read_text())
                    servers = _parse_server_list(data)
                    for s in servers:
                        discovered[s.name] = s
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning(f"Failed to parse {path}: {e}")

    return list(discovered.values())


def _parse_server_list(data: Any) -> list[MCPServerInfo]:
    """Parse JSON data into a list of MCPServerInfo objects.

    Accepts both a list of server configs and a dict keyed by server name.
    """
    servers: list[MCPServerInfo] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "name" in item:
                server = MCPServerInfo(**item)
                server.installed = _check_command_available(server.command)
                servers.append(server)
    elif isinstance(data, dict):
        for name, item in data.items():
            if isinstance(item, dict):
                server = MCPServerInfo(name=name, **item)
                server.installed = _check_command_available(server.command)
                servers.append(server)
    return servers


# ── Registry ─────────────────────────────────────────────────────────────────


class MCPRegistry:
    """Local registry of MCP server configurations.

    Stores servers in ~/.chainforge/mcp_servers.json.

    Args:
        path: Custom path for the registry file.
    """

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else Path.home() / ".chainforge" / "mcp_servers.json"
        self._servers: dict[str, MCPServerInfo] = {}
        self._load()
        # Auto-discover and merge on init
        self._auto_discover()

    def _load(self) -> None:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                for item in data:
                    server = MCPServerInfo(**item)
                    self._servers[server.name] = server
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to load MCP registry: {e}")

    def _auto_discover(self) -> None:
        """Auto-discover servers and merge with registry."""
        discovered = discover_servers()
        for server in discovered:
            if server.name not in self._servers:
                self._servers[server.name] = server

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = [s.model_dump(mode="json") for s in self._servers.values()]
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def list(self) -> list[MCPServerInfo]:
        return list(self._servers.values())

    def get(self, name: str) -> MCPServerInfo | None:
        return self._servers.get(name)

    def search(self, query: str) -> list[MCPServerInfo]:
        q = query.lower()
        return [
            s for s in self._servers.values()
            if q in s.name.lower() or q in s.description.lower() or any(q in tag.lower() for tag in s.tags)
        ]

    def add(self, server: MCPServerInfo) -> None:
        self._servers[server.name] = server
        self.save()
        logger.info(f"Added MCP server: {server.name}")

    def remove(self, name: str) -> bool:
        if name in self._servers:
            del self._servers[name]
            self.save()
            return True
        return False

    def add_builtin(self, name: str) -> MCPServerInfo | None:
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
        server = MCPServerInfo(
            name=name, description=description, command=command,
            transport=transport, source="custom", tags=tags or [],
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
    if not command:
        return False
    first_word = command.split()[0]
    return shutil.which(first_word) is not None
