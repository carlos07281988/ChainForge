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
"""ToolAgent — agent specialized for heavy tool orchestration."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from chainforge.core.agent import Agent
from chainforge.core.llm import LLM
from chainforge.core.message import Message
from chainforge.core.stream import Stream
from chainforge.core.tool import Tool

TOOL_AGENT_SYSTEM = """You are an expert tool orchestrator. Your job is to:
1. Understand the user's request
2. Break it down into tool operations
3. Execute tools in the correct order
4. Combine results into a clear answer
"""


class ToolAgent(BaseModel):
    """High-level tool orchestration agent."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    llm: LLM = Field(description="LLM provider")
    tools: list[Tool] = Field(default_factory=list, description="Available tools")
    max_iterations: int = Field(default=20)
    temperature: float | None = Field(default=None)
    max_tokens: int | None = Field(default=None)

    async def run(self, prompt: str | list[Message], *, context: dict[str, Any] | None = None) -> Stream:
        if isinstance(prompt, str):
            messages = [Message.system(TOOL_AGENT_SYSTEM), Message.user(prompt)]
        else:
            messages = list(prompt)
        agent = Agent(llm=self.llm, tools=self.tools, system_prompt=None,
                      max_iterations=self.max_iterations, temperature=self.temperature,
                      max_tokens=self.max_tokens)
        return await agent.run(messages, context=context)
