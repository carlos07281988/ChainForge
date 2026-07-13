"""Agent — the core execution loop for LLM + Tools with streaming."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from functools import partial
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from chainforge.core.errors import MaxIterationsError
from chainforge.core.llm import LLM, LLMResponse
from chainforge.core.message import Message, ToolCall
from chainforge.core.middleware import MiddlewareChain
from chainforge.core.state import AgentState, StateTracker
from chainforge.core.stream import EventType, Stream, StreamEvent
from chainforge.core.tool import Tool


class Agent(BaseModel):
    """An agent that uses an LLM and tools to accomplish tasks.

    Emits rich streaming events including state transitions, tool calls,
    text content, and errors. Use the `state` event type to track
    real-time agent progress.
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
            return Message.tool_result(tc.id, tc.name, f"Unknown tool: {tc.name}", is_error=True)
        try:
            result = await tool_obj.run(**tc.args)
            return Message.tool_result(tc.id, tc.name, str(result))
        except Exception as e:
            return Message.tool_result(tc.id, tc.name, str(e), is_error=True)

    async def _execute_tool_calls(self, tool_calls: list[dict]) -> list[Message]:
        tcs = [
            ToolCall(id=td.get("id", ""), name=td["function"]["name"], args=td["function"].get("arguments", {}))
            for td in tool_calls
        ]
        if self.parallel_tool_calls and len(tcs) > 1:
            results = await asyncio.gather(*[self._execute_tool(tc) for tc in tcs], return_exceptions=True)
            msgs = []
            for tc, result in zip(tcs, results):
                if isinstance(result, Exception):
                    msgs.append(Message.tool_result(tc.id, tc.name, str(result), is_error=True))
                else:
                    msgs.append(result)
            return msgs
        return [await self._execute_tool(tc) for tc in tcs]

    def _emit_state(self, tracker: StateTracker, to_state: AgentState, **kw) -> list[StreamEvent]:
        t = tracker.transition(to_state, **kw)
        data = {
            "state": to_state.value,
            "from_state": t.from_state.value if t.from_state else None,
            "iteration": t.iteration,
            "depth": t.depth,
        }
        if kw.get("tool_name"):
            data["tool_name"] = kw["tool_name"]
        return [StreamEvent(type=EventType.state, content=t.message or to_state.value, data=data)]

    async def _run_loop(
        self,
        messages: list[Message],
        ctx: dict[str, Any] | None = None,
        *,
        tracker: StateTracker | None = None,
    ) -> AsyncIterator[StreamEvent]:
        tool_specs = [t.spec for t in self.tools] if self.tools else None
        tracker = tracker or StateTracker()

        for iteration in range(self.max_iterations):
            """emit state: thinking"""
            for e in self._emit_state(tracker, AgentState.thinking, iteration=iteration):
                yield e

            kwargs = {}
            if self.max_tokens is not None:
                kwargs["max_tokens"] = self.max_tokens
            if self.temperature is not None:
                kwargs["temperature"] = self.temperature

            response = await self.llm.generate(messages, tools=tool_specs, **kwargs)
            saw_tool_calls = bool(response.tool_calls)

            if response.content:
                yield StreamEvent(type=EventType.text, content=response.content)

            if saw_tool_calls:
                for e in self._emit_state(tracker, AgentState.executing_tool, iteration=iteration):
                    yield e

                for tc_data in response.tool_calls:
                    yield StreamEvent(
                        type=EventType.tool_call,
                        data={
                            "name": tc_data["function"]["name"],
                            "args": tc_data["function"].get("arguments", {}),
                            "id": tc_data.get("id", ""),
                        },
                    )

                result_msgs = await self._execute_tool_calls(response.tool_calls)

                for e in self._emit_state(tracker, AgentState.observing, iteration=iteration):
                    yield e

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

            for e in self._emit_state(tracker, AgentState.responding, iteration=iteration):
                yield e
            yield StreamEvent(type=EventType.done, content=response.content)
            for e in self._emit_state(tracker, AgentState.done, iteration=iteration):
                yield e
            return

        raise MaxIterationsError(f"Agent exceeded {self.max_iterations} iterations")

    async def run(
        self,
        prompt: str | list[Message],
        *,
        context: dict[str, Any] | None = None,
        response_model: type[BaseModel] | None = None,
    ) -> Stream:
        """Execute the agent with the given prompt.

        Args:
            prompt: String prompt or list of messages.
            context: Optional context dict (passed to middleware).
            response_model: Optional Pydantic model for structured output.

        Returns a Stream of events with typed StateEvent transitions.
        """
        if isinstance(prompt, str):
            messages: list[Message] = []
            if self.system_prompt:
                messages.append(Message.system(self.system_prompt))
            messages.append(Message.user(prompt))
        else:
            messages = list(prompt)

        ctx = context or {}
        if response_model is not None:
            ctx["_response_model"] = response_model

        tracker = StateTracker()
        # Create a handler that accepts (messages, ctx) for middleware chain,
        # with tracker pre-bound via closure
        async def _handler(msgs: list[Message], c: dict[str, Any]) -> AsyncIterator[StreamEvent]:
            async for event in self._run_loop(msgs, c, tracker=tracker):
                yield event

        if self.middlewares:
            chain = MiddlewareChain(self.middlewares)
            return Stream(chain.run(messages, ctx, _handler), response_model=response_model)

        return Stream(_handler(messages, ctx), response_model=response_model)
