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
"""MCP client — consume tools from Model Context Protocol servers.

MCP (Model Context Protocol) allows agents to discover and use tools
from external servers, enabling dynamic tool composition.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from chainforge.core.tool import Tool, ToolSpec


class MCPServer(BaseModel):
    """Configuration for an MCP server."""

    name: str = Field(description="Server name")
    command: str = Field(default="", description="Shell command to start server")
    url: str | None = Field(default=None, description="HTTP URL for remote server")
    transport: str = Field(default="stdio", description="Transport: stdio or sse")


class MCPTool(Tool):
    """A tool proxied from an MCP server."""

    def __init__(self, server: MCPServer, spec: ToolSpec, client: Any):
        self._server = server
        self._spec = spec
        self._client = client

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    async def run(self, **kwargs: Any) -> str:
        try:
            return await self._client.call_tool(self._spec.name, kwargs)
        except Exception as e:
            return f"MCP error: {e}"

    def __call__(self, **kwargs: Any) -> str:
        from chainforge.core.utils import run_sync
        return run_sync(self.run(**kwargs))


class MCPClient(BaseModel):
    """Client that connects to MCP servers and exposes their tools.

    Usage:
        client = MCPClient()
        await client.connect(MCPServer(name="filesystem", command="npx @anthropic/mcp-filesystem"))
        tools = await client.list_tools()
        agent = Agent(llm=llm, tools=tools)
    """

    servers: dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True

    async def connect(self, server: MCPServer) -> None:
        """Connect to an MCP server and discover its tools."""
        if server.transport == "stdio":
            await self._connect_stdio(server)
        elif server.transport == "sse" and server.url:
            await self._connect_sse(server)
        else:
            raise ValueError(f"Unsupported transport: {server.transport}")

    async def _connect_stdio(self, server: MCPServer) -> None:
        import asyncio

        proc = await asyncio.create_subprocess_shell(
            server.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self.servers[server.name] = proc

    async def _connect_sse(self, server: MCPServer) -> None:
        import httpx

        client = httpx.AsyncClient(base_url=server.url)
        self.servers[server.name] = client

    async def list_tools(self) -> list[MCPTool]:
        """List all tools from connected MCP servers."""
        tools: list[MCPTool] = []
        for name, client in self.servers.items():
            if isinstance(client, dict):  # stub
                pass
            try:
                # Query the MCP server for tool list
                result = await self._request(name, "list_tools")
                server_info = MCPServer(name=name, command="")
                for tool_data in result:
                    spec = ToolSpec(
                        name=tool_data["name"],
                        description=tool_data.get("description", ""),
                        parameters=tool_data.get("input_schema", {"type": "object", "properties": {}}),
                    )
                    tools.append(MCPTool(server=server_info, spec=spec, client=client))
            except Exception:
                pass
        return tools

    async def _request(self, server_name: str, method: str, params: dict | None = None) -> Any:
        """Send a JSON-RPC request to an MCP server."""
        import asyncio

        proc = self.servers.get(server_name)
        if proc is None:
            raise ConnectionError(f"Server {server_name} not connected")

        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {},
        }
        if isinstance(proc, asyncio.subprocess.Process):
            request_bytes = (json.dumps(request) + "\n").encode()
            proc.stdin.write(request_bytes)
            await proc.stdin.drain()
            line = await asyncio.wait_for(proc.stdout.readline(), timeout=10)
            response = json.loads(line)
            if "result" in response:
                return response["result"]
            raise Exception(response.get("error", str(response)))

        # httpx client (SSE transport)
        import httpx

        client: httpx.AsyncClient = proc
        resp = await client.post("/rpc", json=request)
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", data)

    async def close(self) -> None:
        """Disconnect all MCP servers."""
        import asyncio

        for name, proc in list(self.servers.items()):
            if isinstance(proc, asyncio.subprocess.Process):
                proc.terminate()
                await proc.wait()
        self.servers.clear()
