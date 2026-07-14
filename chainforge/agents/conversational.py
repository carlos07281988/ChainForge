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
"""ConversationalAgent — 多轮对话 + 自动上下文管理。

内置对话历史管理，支持:
- 自动超出长度时摘要压缩
- 最近 N 轮保留完整消息
- 系统提示随对话演进
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from logging import INFO
from typing import Any

from pydantic import BaseModel, Field, ConfigDict, PrivateAttr

from chainforge.core.agent import Agent
from chainforge.core.llm import LLM
from chainforge.core.message import Message
from chainforge.core.stream import EventType, Stream, StreamEvent
from chainforge.core.tool import Tool
from chainforge.logging import get_logger, log_data
from chainforge.memory import BufferMemory, SummaryMemory

logger = get_logger("agents.conversational")

SUMMARY_PROMPT = """Summarize the conversation so far, keeping key information,
decisions, and context for future reference."""


class ConversationalAgent(BaseModel):
    """Agent specialized for multi-turn conversation with automatic context management.

    Usage:
        agent = ConversationalAgent(
            llm=OpenAIProvider(),
            tools=[search],
            max_turns_before_summary=6,
        )
        async for event in await agent.run("Hello!"):
            ...
        async for event in await agent.run("What did I just ask?"):
            ...
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    llm: LLM = Field(description="LLM provider")
    tools: list[Tool] = Field(default_factory=list, description="Available tools")
    system_prompt: str | None = Field(default="You are a helpful assistant in a conversation.")
    max_turns_before_summary: int = Field(default=6, description="Turns before compressing history")
    max_iterations: int = Field(default=8, description="Max iterations per turn")
    temperature: float | None = Field(default=None)

    _buffer: Any = PrivateAttr()
    _summary: Any = PrivateAttr()

    def model_post_init(self, __context):
        self._buffer = BufferMemory(max_messages=self.max_turns_before_summary * 2)
        self._summary = SummaryMemory(max_recent=self.max_turns_before_summary)

    async def run(self, prompt: str | list[Message], *, context: dict[str, Any] | None = None) -> Stream:
        async def _generate() -> AsyncIterator[StreamEvent]:
            user_prompt = prompt if isinstance(prompt, str) else (prompt[-1].content if prompt[-1].content else "")
            log_data(logger, INFO, "Conversational turn started", data={"input_length": len(user_prompt)})

            yield StreamEvent(type=EventType.state, content="thinking",
                              data={"state": "thinking", "turn": len(self._buffer.get_history()) // 2 + 1})

            # Build context: summary + recent messages + new input
            context_msgs = []
            summary_msgs = await self._summary.load()
            if summary_msgs:
                context_msgs.extend(summary_msgs)

            recent = self._buffer.get_history()
            # Skip the summary message from buffer if summary memory also has it
            if context_msgs and recent and context_msgs[-1].content != recent[0].content:
                pass  # both have content
            context_msgs.extend(recent)

            # Add new user input
            if isinstance(prompt, list):
                context_msgs.extend(prompt)
            else:
                if self.system_prompt and not context_msgs:
                    context_msgs.append(Message.system(self.system_prompt))
                context_msgs.append(Message.user(user_prompt))

            # Execute agent
            turn_agent = Agent(
                llm=self.llm,
                tools=self.tools,
                system_prompt=None,  # Already in context_msgs if needed
                max_iterations=self.max_iterations,
                temperature=self.temperature,
            )
            turn_stream = await turn_agent.run(context_msgs, context=context)
            parts = []
            async for ev in turn_stream:
                if ev.type == EventType.text and ev.content:
                    parts.append(ev.content)
                yield ev

            response = "".join(parts)

            # Save to memory
            await self._buffer.save([Message.user(user_prompt), Message.assistant(response)])
            await self._summary.save([Message.user(user_prompt), Message.assistant(response)])

            # Check if we need to compress
            if len(self._buffer.get_history()) >= self.max_turns_before_summary * 2:
                yield StreamEvent(type=EventType.status, content="Compressing conversation history...")
                summary_resp = await self.llm.generate([
                    Message.system(SUMMARY_PROMPT),
                    Message.user(f"Conversation:\n{chr(10).join(m.content or '' for m in self._buffer.get_history()[:10])}"),
                ])
                if summary_resp.content:
                    self._summary.summary = summary_resp.content
                    self._buffer.clear()
                    log_data(logger, INFO, "Conversation compressed", data={"summary_length": len(summary_resp.content)})

            yield StreamEvent(type=EventType.state, content="done", data={"state": "done"})
            yield StreamEvent(type=EventType.done)

        return Stream(_generate())

    def clear_history(self):
        """Reset conversation."""
        self._buffer.clear()
        self._summary.summary = ""
        self._summary.recent_messages = []
