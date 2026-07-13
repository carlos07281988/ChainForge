"""Agent — the core execution loop for LLM + Tools with streaming."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from chainforge.core.errors import MaxIterationsError
from chainforge.core.llm import LLM, LLMResponse
from chainforge.core.message import Message, ToolCall
from chainforge.core.middleware import MiddlewareChain
from chainforge.core.stream import EventType, Stream, StreamEvent
from chainforge.core.tool import Tool


class Agent(BaseModel):
    """An agent that uses an LLM and tools to accomplish tasks.

    Core execution loop:
    1. Send messages + tool schemas to LLM
    2. If LLM returns tool calls → execute tools → append results → repeat
    3. If LLM returns text → done

    Usage:
        agent = Agent(
            llm=OpenAI(model="gpt-4"),
            tools=[get_weather, search],
        )
        async for event in agent.run("Weather in Beijing?"):
            ...
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    llm: LLM = Field(description="LLM provider")
    tools: list[Tool] = Field(default_factory=list, description="Available tools")
    system_prompt: str | None = Field(default=None, description="System instructions")
    max_iterations: int = Field(default=10, description="Max tool-use iterations")
    max_tokens: int | None = Field(default=None, description="Max tokens per response")
    temperature: float | None = Field(default=None, description="LLM temperature")
    middlewares: list | None = Field(default=None, description="Middleware list")
    parallel_tool_calls: bool = Field(default=True, description="Execute independent tool calls in parallel")

    def _get_tool_map(self) -> dict[str, Tool]:
        return {t.spec.name: t for t in self.tools}

    async def _execute_tool(self, tc: ToolCall) -> Message:
        tool_map = self._get_tool_map()
        tool_obj = tool_map.get(tc.name)
        if tool_obj is None:
            return Message.tool_result(
                tool_call_id=tc.id,
                name=tc.name,
                content=f"Unknown tool: {tc.name}",
                is_error=True,
            )
        try:
            result = await tool_obj.run(**tc.args)
            return Message.tool_result(
                tool_call_id=tc.id,
                name=tc.name,
                content=str(result),
            )
        except Exception as e:
            return Message.tool_result(
                tool_call_id=tc.id,
                name=tc.name,
                content=str(e),
                is_error=True,
            )

    async def _execute_tool_calls(self, tool_calls: list[dict]) -> list[Message]:
        """Execute tool calls, optionally in parallel for independent calls."""
        tcs = [
            ToolCall(
                id=tc_data.get("id", ""),
                name=tc_data["function"]["name"],
                args=tc_data["function"].get("arguments", {}),
            )
            for tc_data in tool_calls
        ]

        if self.parallel_tool_calls and len(tcs) > 1:
            # Check independence: if tools have different names or different args,
            # we can safely execute in parallel
            results = await asyncio.gather(
                *[self._execute_tool(tc) for tc in tcs],
                return_exceptions=True,
            )
            msgs = []
            for tc, result in zip(tcs, results):
                if isinstance(result, Exception):
                    msgs.append(Message.tool_result(tc.id, tc.name, str(result), is_error=True))
                else:
                    msgs.append(result)
            return msgs

        return [await self._execute_tool(tc) for tc in tcs]

    async def _run_loop(self, messages: list[Message]) -> AsyncIterator[StreamEvent]:
        tool_specs = [t.spec for t in self.tools] if self.tools else None

        for iteration in range(self.max_iterations):
            kwargs = {}
            if self.max_tokens is not None:
                kwargs["max_tokens"] = self.max_tokens
            if self.temperature is not None:
                kwargs["temperature"] = self.temperature

            response = await self.llm.generate(messages, tools=tool_specs, **kwargs)
            saw_tool_calls = bool(response.tool_calls)

            # Yield streaming agent state
            yield StreamEvent(
                type=EventType.status,
                content=f"iteration_{iteration + 1}",
                data={"iteration": iteration + 1, "tool_calls": len(response.tool_calls) if response.tool_calls else 0},
            )

            if response.content:
                yield StreamEvent(type=EventType.text, content=response.content)

            if saw_tool_calls:
                # Emit tool_call events
                for tc_data in response.tool_calls:
                    yield StreamEvent(
                        type=EventType.tool_call,
                        data={
                            "name": tc_data["function"]["name"],
                            "args": tc_data["function"].get("arguments", {}),
                            "id": tc_data.get("id", ""),
                        },
                    )

                # Execute (parallel)
                result_msgs = await self._execute_tool_calls(response.tool_calls)

                # Emit tool_result events and append to conversation
                for msg in result_msgs:
                    messages.append(msg)
                    yield StreamEvent(
                        type=EventType.tool_result,
                        data={
                            "name": msg.name or "",
                            "content": msg.content or "",
                            "is_error": msg.metadata.get("is_error", False),
                        },
                    )
                continue

            yield StreamEvent(type=EventType.done, content=response.content)
            return

        raise MaxIterationsError(f"Agent exceeded {self.max_iterations} iterations")

    async def run(
        self,
        prompt: str | list[Message],
        *,
        context: dict[str, Any] | None = None,
    ) -> Stream:
        """Execute the agent with the given prompt.

        Returns a Stream of events. The caller iterates over it asynchronously.
        """
        if isinstance(prompt, str):
            messages: list[Message] = []
            if self.system_prompt:
                messages.append(Message.system(self.system_prompt))
            messages.append(Message.user(prompt))
        else:
            messages = list(prompt)

        ctx = context or {}

        if self.middlewares:
            chain = MiddlewareChain(self.middlewares)
            return Stream(chain.run(messages, ctx, self._run_loop))

        return Stream(self._run_loop(messages))
