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
"""PermissionPolicy — minimal-privilege policy for agent tools."""
from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from chainforge.core.message import Message
from chainforge.core.stream import EventType, StreamEvent
from chainforge.logging import get_logger

logger = get_logger("enterprise.supply_chain.policy")


class PermissionPolicy(BaseModel):
    """A minimal-privilege tool permission policy.

    Usage:
        policy = PermissionPolicy(
            allowed_tools=["query_db", "send_email"],
            blocked_tools=["delete_file"],
        )

        # Save as YAML for CI/CD
        policy.to_yaml("security/policies/my_agent.yaml")

        # Enforce at runtime
        agent = Agent(llm=llm, tools=[...], middlewares=[policy.as_middleware()])
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    allowed_tools: list[str] = Field(default_factory=list)
    blocked_tools: list[str] = Field(default_factory=list)
    mcp_constraints: dict[str, dict[str, Any]] = Field(default_factory=dict)

    def to_yaml(self, path: str | None = None) -> str:
        """Export policy as a YAML string, optionally saving to disk.

        Args:
            path: Optional file path to write the YAML to.

        Returns:
            YAML string representation.
        """
        data = self.model_dump()
        yaml_str = yaml.dump(data, default_flow_style=False, allow_unicode=True)
        if path:
            Path(path).write_text(yaml_str, encoding="utf-8")
        return yaml_str

    def as_middleware(self) -> Callable[..., AsyncIterator[StreamEvent]]:
        """Create an agent middleware that enforces this policy.

        Intercepts tool calls and blocks those not in the allowed list
        or explicitly blocked.

        Returns:
            An async middleware function.
        """
        allowed: set[str] = set(self.allowed_tools)
        blocked: set[str] = set(self.blocked_tools)

        async def _mw(
            messages: list[Message],
            ctx: dict[str, Any],
            next_handler: Any,
        ) -> AsyncIterator[StreamEvent]:
            async for event in next_handler(messages, ctx):
                # Check tool call events
                if event.type == EventType.tool_call:
                    tool_name: str = event.data.get("name", "") if event.data else ""
                    if tool_name:
                        if tool_name in blocked:
                            logger.warning(f"Blocked tool: {tool_name}")
                            yield StreamEvent.error(
                                f"Tool '{tool_name}' is blocked by security policy",
                            )
                            continue
                        if allowed and tool_name not in allowed:
                            logger.warning(f"Tool not in allowlist: {tool_name}")
                            yield StreamEvent.error(
                                f"Tool '{tool_name}' is not in the allowlist",
                            )
                            continue
                yield event

        return _mw
