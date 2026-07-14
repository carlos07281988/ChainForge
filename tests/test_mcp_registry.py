# Copyright 2024 ChainForge Contributors
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
"""Tests for the MCP Tool Registry."""

import json
import tempfile
from pathlib import Path

import pytest

from chainforge.mcp.registry import (
    MCPRegistry,
    MCPServerInfo,
    get_builtin_names,
    get_builtin,
    BUILTIN_SERVERS,
)


class TestBuiltinServers:
    def test_get_builtin_names(self):
        names = get_builtin_names()
        assert "filesystem" in names
        assert len(names) > 0

    def test_get_builtin(self):
        fs = get_builtin("filesystem")
        assert fs is not None
        assert fs.name == "filesystem"
        assert fs.command.startswith("npx")
        assert len(fs.tools) > 0

    def test_get_builtin_nonexistent(self):
        assert get_builtin("nonexistent") is None

    def test_builtin_servers_dict(self):
        assert "sqlite" in BUILTIN_SERVERS
        assert "github" in BUILTIN_SERVERS
        assert "web_search" in BUILTIN_SERVERS
        assert "playwright" in BUILTIN_SERVERS

    def test_all_builtins_have_required_fields(self):
        for name, data in BUILTIN_SERVERS.items():
            assert "name" in data
            assert "command" in data
            assert "description" in data
            assert "transport" in data
            assert data["name"] == name


class TestMCPServerInfo:
    def test_defaults(self):
        info = MCPServerInfo(name="test", command="echo hello")
        assert info.name == "test"
        assert info.description == ""
        assert info.transport == "stdio"
        assert info.installed is False
        assert info.tags == []
        assert info.tools == []

    def test_full(self):
        info = MCPServerInfo(
            name="full",
            description="Full test",
            command="npx test",
            transport="sse",
            source="npm",
            tags=["test", "demo"],
            tools=["tool1", "tool2"],
            installed=True,
        )
        assert info.name == "full"
        assert info.transport == "sse"
        assert len(info.tools) == 2


class TestMCPRegistry:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.registry_path = Path(self.tmpdir) / "mcp_test.json"

    def test_create_registry(self):
        reg = MCPRegistry(path=self.registry_path)
        assert reg.count == 0

    def test_add_builtin(self):
        reg = MCPRegistry(path=self.registry_path)
        server = reg.add_builtin("filesystem")
        assert server is not None
        assert server.name == "filesystem"
        assert reg.count == 1

    def test_add_builtin_nonexistent(self):
        reg = MCPRegistry(path=self.registry_path)
        result = reg.add_builtin("nonexistent")
        assert result is None
        assert reg.count == 0

    def test_add_custom(self):
        reg = MCPRegistry(path=self.registry_path)
        server = reg.add_custom(
            "my-server",
            "python my_server.py",
            description="Custom server",
            tags=["custom"],
        )
        assert server.name == "my-server"
        assert reg.count == 1

    def test_list(self):
        reg = MCPRegistry(path=self.registry_path)
        reg.add_builtin("filesystem")
        reg.add_builtin("github")
        servers = reg.list()
        assert len(servers) == 2

    def test_get(self):
        reg = MCPRegistry(path=self.registry_path)
        reg.add_builtin("filesystem")
        server = reg.get("filesystem")
        assert server is not None
        assert server.name == "filesystem"

    def test_get_nonexistent(self):
        reg = MCPRegistry(path=self.registry_path)
        assert reg.get("nonexistent") is None

    def test_remove(self):
        reg = MCPRegistry(path=self.registry_path)
        reg.add_builtin("filesystem")
        assert reg.remove("filesystem") is True
        assert reg.count == 0

    def test_remove_nonexistent(self):
        reg = MCPRegistry(path=self.registry_path)
        assert reg.remove("nonexistent") is False

    def test_search(self):
        reg = MCPRegistry(path=self.registry_path)
        reg.add_builtin("filesystem")
        reg.add_builtin("github")
        reg.add_builtin("sqlite")
        results = reg.search("file")
        assert len(results) >= 1
        assert results[0].name == "filesystem"

    def test_search_by_tag(self):
        reg = MCPRegistry(path=self.registry_path)
        reg.add_builtin("sqlite")
        results = reg.search("database")
        assert len(results) >= 1

    def test_persistence(self):
        reg1 = MCPRegistry(path=self.registry_path)
        reg1.add_builtin("filesystem")

        # Create a new registry instance with the same path
        reg2 = MCPRegistry(path=self.registry_path)
        assert reg2.count == 1
        assert reg2.get("filesystem") is not None

    def test_stats(self):
        reg = MCPRegistry(path=self.registry_path)
        reg.add_builtin("filesystem")
        stats = reg.stats()
        assert stats["total"] == 1
        assert "path" in stats

    def test_save_and_load_custom_server(self):
        reg1 = MCPRegistry(path=self.registry_path)
        reg1.add_custom("my-api", "node server.js")

        reg2 = MCPRegistry(path=self.registry_path)
        server = reg2.get("my-api")
        assert server is not None
        assert server.command == "node server.js"

    def test_add_builtin_twice(self):
        reg = MCPRegistry(path=self.registry_path)
        reg.add_builtin("filesystem")
        reg.add_builtin("filesystem")  # Overwrites
        assert reg.count == 1
