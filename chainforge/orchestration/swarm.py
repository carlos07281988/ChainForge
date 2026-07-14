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
"""Swarm — multiple agents working together on a shared task.

In a Swarm, agents can either:
- Work in parallel (fan-out), each handling a sub-task
- Work in sequence (pipeline), passing results between them
- Work in a conference pattern, each contributing to a shared context
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from chainforge.core.agent import Agent
from chainforge.core.message import Message
from chainforge.core.stream import EventType, Stream, StreamEvent


class SwarmMode(str, Enum):
    parallel = "parallel"
    sequential = "sequential"
    conference = "conference"


class Swarm(BaseModel):
    """A group of agents working together on a task.

    Modes:
    - parallel: All agents receive the same prompt, results are combined
    - sequential: Each agent passes its output to the next (pipeline)
    - conference: Agents take turns, each building on the shared conversation
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    agents: list[Agent] = Field(description="List of agents in the swarm")
    mode: SwarmMode = Field(default=SwarmMode.sequential)
    name: str = Field(default="swarm")

    async def run(self, prompt: str | list[Message], *, context: dict[str, Any] | None = None) -> Stream:
        """Execute the swarm on the given prompt."""

        async def _generate() -> AsyncIterator[StreamEvent]:
            yield StreamEvent(type=EventType.status, content=f"Swarm '{self.name}' started (mode={self.mode.value})")

            if self.mode == SwarmMode.parallel:
                async for event in self._run_parallel(prompt, context):
                    yield event

            elif self.mode == SwarmMode.sequential:
                async for event in self._run_sequential(prompt, context):
                    yield event

            elif self.mode == SwarmMode.conference:
                async for event in self._run_conference(prompt, context):
                    yield event

            yield StreamEvent(type=EventType.done)

        return Stream(_generate())

    async def _run_parallel(self, prompt: str | list[Message], context: dict | None) -> AsyncIterator[StreamEvent]:
        import asyncio

        yield StreamEvent(type=EventType.status, content=f"Running {len(self.agents)} agents in parallel")

        async def _run_one(i: int, agent: Agent) -> list[StreamEvent]:
            events: list[StreamEvent] = []
            stream = await agent.run(prompt, context=context)
            async for event in stream:
                if event.type != EventType.done:
                    events.append(event)
            return events

        results = await asyncio.gather(*[_run_one(i, a) for i, a in enumerate(self.agents)])

        for i, (agent, events) in enumerate(zip(self.agents, results)):
            yield StreamEvent(type=EventType.status, content=f"Agent {i} ({type(agent.llm).__name__}) results:")
            for event in events:
                yield event

    async def _run_sequential(self, prompt: str | list[Message], context: dict | None) -> AsyncIterator[StreamEvent]:
        current_prompt = prompt
        for i, agent in enumerate(self.agents):
            yield StreamEvent(type=EventType.status, content=f"Agent {i + 1}/{len(self.agents)} starting")

            stream = await agent.run(current_prompt, context=context)
            collected_parts: list[str] = []
            async for event in stream:
                if event.type == EventType.text and event.content:
                    collected_parts.append(event.content)
                yield event

            # Pass result to next agent
            if collected_parts:
                combined = "".join(collected_parts)
                if isinstance(current_prompt, str):
                    current_prompt = f"Previous result:\n{combined}\n\nContinue from here:"
                else:
                    current_prompt = current_prompt + [Message.assistant(combined)]

    async def _run_conference(self, prompt: str | list[Message], context: dict | None) -> AsyncIterator[StreamEvent]:
        """Agents take turns, each building on the conversation."""
        if isinstance(prompt, str):
            messages = [Message.user(prompt)]
        else:
            messages = list(prompt)

        for i, agent in enumerate(self.agents):
            yield StreamEvent(type=EventType.status, content=f"Agent {i + 1} contributing (conference round {i})")

            stream = await agent.run(messages, context=context)
            async for event in stream:
                if event.type == EventType.text and event.content:
                    messages.append(Message.assistant(event.content))
                yield event
