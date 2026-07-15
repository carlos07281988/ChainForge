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
"""OpenAPIToolkit — convert OpenAPI specs into callable tools.

Usage:
    from chainforge.tools.openapi import OpenAPIToolkit

    toolkit = OpenAPIToolkit.from_url("https://api.example.com/openapi.json")
    tools = toolkit.to_tools()

    agent = Agent(llm=llm, tools=tools)
"""

from __future__ import annotations

import json
from typing import Any

from chainforge.core.tool import ToolSpec, FunctionTool
from chainforge.logging import get_logger

logger = get_logger("tools.openapi")


class OpenAPIToolkit:
    """Convert OpenAPI specs to ChainForge Tool instances.

    Supports OpenAPI 3.x specs. Each operation becomes a tool named
    {operationId} or {method}_{path}.
    """

    def __init__(self, spec: dict[str, Any], base_url: str | None = None):
        self._spec = spec
        self._base_url = base_url or spec.get("servers", [{}])[0].get("url", "")

    @classmethod
    def from_url(cls, url: str, **kwargs) -> "OpenAPIToolkit":
        """Load an OpenAPI spec from a URL."""
        import httpx
        resp = httpx.get(url, **kwargs)
        resp.raise_for_status()
        return cls(spec=resp.json())

    @classmethod
    def from_file(cls, path: str) -> "OpenAPIToolkit":
        """Load an OpenAPI spec from a local JSON file."""
        with open(path) as f:
            return cls(spec=json.load(f))

    @classmethod
    def from_dict(cls, spec: dict) -> "OpenAPIToolkit":
        """Create from an already-parsed spec dict."""
        return cls(spec=spec)

    def to_tools(self) -> list[FunctionTool]:
        """Convert all operations to ChainForge tools."""
        tools: list[FunctionTool] = []
        paths = self._spec.get("paths", {})

        for path, path_item in paths.items():
            for method in ("get", "post", "put", "patch", "delete"):
                operation = path_item.get(method)
                if operation is None:
                    continue

                tool = self._build_tool(method, path, operation)
                if tool is not None:
                    tools.append(tool)

        logger.info(f"Built {len(tools)} tools from OpenAPI spec")
        return tools

    def _build_tool(self, method: str, path: str, operation: dict) -> FunctionTool | None:
        operation_id = operation.get("operationId", f"{method}_{path.replace('/', '_').strip('_')}")
        summary = operation.get("summary", operation_id)
        description = operation.get("description", summary)

        # Build parameters schema
        parameters: dict[str, Any] = {"type": "object", "properties": {}, "required": []}

        # Path/query/header params
        for param in operation.get("parameters", []):
            name = param["name"]
            param_schema = param.get("schema", {"type": "string"})
            parameters["properties"][name] = {
                "type": param_schema.get("type", "string"),
                "description": param.get("description", ""),
            }
            if param.get("required", False):
                parameters["required"].append(name)

        # Request body
        request_body = operation.get("requestBody", {})
        content = request_body.get("content", {})
        if "application/json" in content:
            body_schema = content["application/json"].get("schema", {})
            if "properties" in body_schema:
                for name, prop in body_schema["properties"].items():
                    parameters["properties"][f"body_{name}"] = {
                        "type": prop.get("type", "string"),
                        "description": prop.get("description", ""),
                    }
            if body_schema.get("required"):
                for r in body_schema["required"]:
                    parameters["required"].append(f"body_{r}")

        async def _execute(**kwargs: Any) -> str:
            import httpx
            url = f"{self._base_url.rstrip('/')}{path}"
            headers = {"Content-Type": "application/json"}
            params = {}
            body = {}

            for key, value in kwargs.items():
                if key.startswith("body_"):
                    body[key[5:]] = value
                else:
                    params[key] = value

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.request(
                    method=method.upper(),
                    url=url,
                    params=params if method in ("get", "delete") else None,
                    json=body if method in ("post", "put", "patch") else None,
                    headers=headers,
                )
                resp.raise_for_status()
                return resp.text[:10000]  # Truncate long responses

        _execute.__name__ = operation_id
        _execute.__doc__ = description

        return FunctionTool(
            _execute,
            name=operation_id,
            description=description[:200],
        )
