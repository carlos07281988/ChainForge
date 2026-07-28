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
"""ChainForge Interop Protocol v1 — framework-agnostic agent communication."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InteropRequest(BaseModel):
    """Standard interop request format — framework-agnostic."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    messages: list[dict[str, str]] = Field(
        default_factory=list, description="OpenAI-format messages"
    )
    tools: list[dict[str, Any]] = Field(
        default_factory=list, description="OpenAI-format tool schemas"
    )
    context: dict[str, Any] = Field(
        default_factory=dict, description="run_id, parent_agent, trace_id, etc."
    )
    protocol_version: str = Field(default="chainforge-interop-v1")


class InteropResponse(BaseModel):
    """Standard interop response."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    content: str = ""
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = Field(default_factory=dict)
    model: str = ""
    error: str | None = None


class InteropProtocol:
    """Defines the JSON Schema for ChainForge Interop Protocol v1.

    This is the wire format that ALL frameworks speak to federate.
    Compatible with OpenAI's chat completion format for easy adoption.

    Endpoint: POST /agent
    Content-Type: application/json
    Accept: text/event-stream (SSE) or application/json (non-streaming)
    """

    VERSION = "chainforge-interop-v1"

    @staticmethod
    def request_schema() -> dict:
        return {
            "type": "object",
            "required": ["messages"],
            "properties": {
                "messages": {"type": "array", "items": {"$ref": "#/definitions/message"}},
                "tools": {"type": "array"},
                "context": {"type": "object"},
                "protocol_version": {
                    "type": "string",
                    "default": "chainforge-interop-v1",
                },
            },
        }

    @staticmethod
    def response_schema() -> dict:
        return {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "tool_calls": {"type": "array"},
                "finish_reason": {"type": "string"},
                "usage": {"type": "object"},
                "model": {"type": "string"},
                "error": {"type": "string", "nullable": True},
            },
        }

    @staticmethod
    def compatible_frameworks() -> list[str]:
        """Known frameworks that speak this protocol (or can be adapted)."""
        return [
            "chainforge",
            "langchain",
            "crewai",
            "autogen",
            "openai-assistants",
            "a2a-v1",
        ]
