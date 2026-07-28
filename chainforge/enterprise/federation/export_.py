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
"""AgentExport — expose a ChainForge agent as a framework-agnostic HTTP endpoint."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from typing import Any

from chainforge.core.message import Message, Role
from chainforge.enterprise.federation.protocol import InteropRequest, InteropResponse
from chainforge.logging import get_logger

logger = get_logger("enterprise.federation")


class AgentExport:
    """Export a ChainForge agent as a framework-agnostic HTTP endpoint.

    Usage:
        export = AgentExport(agent=my_agent)
        export.serve(port=9100)   # starts HTTP server

        # Or get the handler for custom integration:
        handler = export.as_handler()
        response = await handler(request_json)
    """

    def __init__(self, agent, protocol: str = "chainforge-interop-v1"):
        self._agent = agent
        self._protocol = protocol
        self._agent_name = getattr(
            agent,
            "name",
            getattr(agent, "llm", {}).__class__.__name__
            if hasattr(agent, "llm")
            else "unknown",
        )

    def as_handler(self) -> Callable:
        """Return an async function(request_dict) -> response_dict that wraps the agent.

        The returned function accepts a dict matching InteropRequest and returns
        a dict matching InteropResponse. Integrators use this to mount the agent
        into FastAPI, Flask, aiohttp, or any other web framework.
        """

        async def handle(req_dict: dict) -> dict:
            try:
                ireq = InteropRequest(**req_dict)
            except Exception as e:
                return InteropResponse(error=f"Invalid request: {e}").model_dump()

            # Convert interop messages to ChainForge Messages
            messages = []
            for m in ireq.messages:
                role = Role(m.get("role", "user"))
                content = m.get("content", "")
                messages.append(Message(role=role, content=str(content)))

            # Run agent
            try:
                stream = await self._agent.run(
                    messages[-1].content if messages else "",
                    **ireq.context,
                )
                output_parts = []
                tool_calls = []
                usage = {}
                model = ""
                async for event in stream:
                    if hasattr(event, "type"):
                        if event.type == "text":
                            output_parts.append(str(event.content or ""))
                        elif event.type == "tool_call":
                            tn = (
                                event.data.get("tool_name", "")
                                if event.data
                                else ""
                            )
                            if tn:
                                tool_calls.append(
                                    {
                                        "name": tn,
                                        "arguments": event.data.get("arguments", {})
                                        if event.data
                                        else {},
                                    }
                                )
                    elif hasattr(event, "content") and event.content:
                        output_parts.append(str(event.content))
                        if hasattr(event, "usage") and event.usage:
                            usage = event.usage
                        if hasattr(event, "model") and event.model:
                            model = event.model

                return InteropResponse(
                    content="".join(output_parts),
                    tool_calls=tool_calls,
                    finish_reason="stop",
                    usage=usage,
                    model=model,
                ).model_dump()
            except Exception as e:
                logger.error(f"Federation export error: {e}")
                return InteropResponse(error=str(e)).model_dump()

        return handle

    def serve(self, port: int = 9100, host: str = "0.0.0.0") -> None:
        """Start a lightweight HTTP server exposing this agent."""
        try:
            import asyncio
            from http.server import BaseHTTPRequestHandler, HTTPServer

            handler_fn = self.as_handler()

            class AgentHandler(BaseHTTPRequestHandler):
                def do_POST(self):
                    content_length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(content_length)
                    try:
                        req = json.loads(body)
                    except json.JSONDecodeError:
                        self.send_response(400)
                        self.end_headers()
                        self.wfile.write(b'{"error":"Invalid JSON"}')
                        return
                    # Run async handler synchronously for simple server
                    loop = asyncio.new_event_loop()
                    try:
                        resp = loop.run_until_complete(handler_fn(req))
                    finally:
                        loop.close()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(resp).encode())

                def do_GET(self):
                    if self.path == "/health":
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(
                            json.dumps(
                                {
                                    "status": "ok",
                                    "protocol": "chainforge-interop-v1",
                                    "agent": self.server.agent_name,
                                }
                            ).encode()
                        )
                    else:
                        self.send_response(404)
                        self.end_headers()

            server = HTTPServer((host, port), AgentHandler)
            server.agent_name = self._agent_name
            logger.info(
                f"Agent exported at http://{host}:{port} (protocol: {self._protocol})"
            )
            print(f"Agent exported at http://{host}:{port}/agent")
            server.serve_forever()
        except ImportError:
            logger.warning(
                "HTTP server not available — use as_handler() for custom integration"
            )
            print(
                "Export ready: use .as_handler() to integrate with your web framework"
            )
