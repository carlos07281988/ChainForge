"""Agent — the core execution loop for LLM + Tools with streaming."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from logging import DEBUG, INFO, WARNING
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, ConfigDict

from chainforge.core.errors import MaxIterationsError
from chainforge.core.llm import LLM, LLMResponse
from chainforge.core.message import Message, ToolCall
from chainforge.core.middleware import MiddlewareChain
from chainforge.core.state import AgentState, StateTracker
from chainforge.core.stream import EventType, Stream, StreamEvent
from chainforge.core.tool import Tool
from chainforge.logging import get_logger, log_data

from chainforge.skills.base import Skill
logger = get_logger("agent")


class Agent(BaseModel):
    """An agent that uses an LLM and tools (and skills) to accomplish tasks.

    Skills are automatically composed into the agent's system prompt
    and their tools are added to the available tool list.

    Usage:
        agent = Agent(
            llm=OpenAIProvider(),
            tools=[get_weather],
            skills=[weather_skill],
        )
        async for event in await agent.run("Weather in Beijing?"):
            ...
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    llm: LLM = Field(description="LLM provider")
    tools: list[Tool] = Field(default_factory=list, description="Available tools")
    skills: list[Skill] = Field(default_factory=list, description="Skills to compose into the agent")
    system_prompt: str | None = Field(default=None, description="System instructions")
    max_iterations: int = Field(default=10, description="Max tool-use iterations")
    max_tokens: int | None = Field(default=None, description="Max tokens per response")
    temperature: float | None = Field(default=None, description="LLM temperature")
    middlewares: list | None = Field(default=None, description="Middleware list")
    parallel_tool_calls: bool = Field(default=True, description="Execute independent tool calls in parallel")
    reasoning: list = Field(default_factory=list, description="Reasoning strategies")

    def _build_system_prompt(self) -> str | None:
        """Compose the full system prompt from user prompt + skill blocks."""
        parts = []
        if self.system_prompt:
            parts.append(self.system_prompt)

        for skill in self.skills:
            block = skill.to_system_block() if hasattr(skill, "to_system_block") else str(skill)
            parts.append(block)

        return "\n\n".join(parts) if parts else None

    def _collect_skill_tools(self) -> list[Tool]:
        """Collect tools from skills."""
        skill_tools = []
        for skill in self.skills:
            if hasattr(skill, "tools"):
                skill_tools.extend(skill.tools)
            # Also add the skill itself as a callable tool
            if hasattr(skill, "to_tool"):
                skill_tools.append(skill.to_tool())
        return skill_tools

    def _all_tools(self) -> list[Tool]:
        """Combine direct tools + skill tools."""
        seen = set()
        result = []
        for t in self.tools + self._collect_skill_tools():
            name = t.spec.name if hasattr(t, "spec") else id(t)
            if name not in seen:
                seen.add(name)
                result.append(t)
        return result

    # ── Rest of Agent unchanged ──────────────────────────────────────────

    def _get_tool_map(self) -> dict[str, Tool]:
        return {t.spec.name: t for t in self._all_tools()}

    async def _execute_tool(self, tc: ToolCall) -> Message:
        tool_map = self._get_tool_map()
        tool_obj = tool_map.get(tc.name)
        if tool_obj is None:
            log_data(logger, WARNING, f"Unknown tool: {tc.name}", data={"tool": tc.name, "available": list(tool_map.keys())})
            return Message.tool_result(tc.id, tc.name, f"Unknown tool: {tc.name}", is_error=True)
        try:
            log_data(logger, DEBUG, f"Executing tool {tc.name}", data={"tool": tc.name, "args": tc.args})
            args = tc.args
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"_raw": args}
            result = await tool_obj.run(**args)
            log_data(logger, DEBUG, f"Tool {tc.name} OK", data={"tool": tc.name, "result_length": len(str(result))})
            return Message.tool_result(tc.id, tc.name, str(result))
        except Exception as e:
            log_data(logger, WARNING, f"Tool {tc.name} failed: {e}", data={"tool": tc.name, "error": str(e)})
            return Message.tool_result(tc.id, tc.name, str(e), is_error=True)

    async def _execute_tool_calls(self, tool_calls: list[dict]) -> list[Message]:
        tcs = [
            ToolCall(id=td.get("id", ""), name=td["function"]["name"], args=td["function"].get("arguments", {}))
            for td in tool_calls
        ]
        if self.parallel_tool_calls and len(tcs) > 1:
            log_data(logger, DEBUG, f"Executing {len(tcs)} tool calls in parallel",
                     data={"tools": [tc.name for tc in tcs]})
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
        log_data(logger, DEBUG, f"state: {to_state.value} (iter={t.iteration})",
                 data={"state": to_state.value, "iteration": t.iteration})
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
        all_tools = self._all_tools()
        tool_specs = [t.spec for t in all_tools] if all_tools else None
        tracker = tracker or StateTracker()

        log_data(logger, INFO, f"Agent loop starting (max_iterations={self.max_iterations})",
                 data={"tools": [t.spec.name for t in all_tools], "llm": str(self.llm.model)})

        for iteration in range(self.max_iterations):
            for e in self._emit_state(tracker, AgentState.thinking, iteration=iteration):
                yield e

            kwargs = {}
            if self.max_tokens is not None:
                kwargs["max_tokens"] = self.max_tokens
            if self.temperature is not None:
                kwargs["temperature"] = self.temperature

            # ── Reasoning: before_llm hook ──────────────────────────────
            for _strategy in self.reasoning:
                try:
                    messages, ctx = await _strategy.before_llm(messages, ctx)
                except Exception:
                    pass

            response = await self.llm.generate(messages, tools=tool_specs, **kwargs)
            
            # ── Reasoning: after_llm hook ──────────────────────────────
            for _strategy in self.reasoning:
                try:
                    response, messages, ctx = await _strategy.after_llm(response, messages, ctx)
                except Exception:
                    pass
            saw_tool_calls = bool(response.tool_calls)

            log_data(logger, DEBUG, f"Iteration {iteration + 1}: tool_calls={len(response.tool_calls) if response.tool_calls else 0}",
                     data={"iteration": iteration + 1, "tool_calls": len(response.tool_calls) if response.tool_calls else 0})

            if response.content:
                yield StreamEvent(type=EventType.text, content=response.content)

            if saw_tool_calls:
                for e in self._emit_state(tracker, AgentState.executing_tool, iteration=iteration):
                    yield e
                for tc_data in response.tool_calls:
                    yield StreamEvent(type=EventType.tool_call, data={
                        "name": tc_data["function"]["name"],
                        "args": tc_data["function"].get("arguments", {}),
                        "id": tc_data.get("id", ""),
                    })
                result_msgs = await self._execute_tool_calls(response.tool_calls)
                for e in self._emit_state(tracker, AgentState.observing, iteration=iteration):
                    yield e
                for msg in result_msgs:
                    messages.append(msg)
                    # ── Reasoning: on_tool_result hook ────────────────
                    for _strategy in self.reasoning:
                        try:
                            msg, messages, ctx = await _strategy.on_tool_result(msg, messages, ctx)
                        except Exception:
                            pass
                    yield StreamEvent(type=EventType.tool_result, data={
                        "name": msg.name or "", "content": msg.content or "",
                        "is_error": msg.metadata.get("is_error", False),
                    })
                continue

            # ── Reasoning: should_stop hook ────────────────────────────
            _should_stop = False
            for _strategy in self.reasoning:
                try:
                    if await _strategy.should_stop(messages, ctx):
                        _should_stop = True
                        break
                except Exception:
                    pass
            if _should_stop:
                break

            for e in self._emit_state(tracker, AgentState.responding, iteration=iteration):
                yield e
            yield StreamEvent(type=EventType.done, content=response.content)
            for e in self._emit_state(tracker, AgentState.done, iteration=iteration):
                yield e
            log_data(logger, INFO, f"Agent finished after {iteration + 1} iterations",
                     data={"iterations": iteration + 1, "response_length": len(response.content or "")})
            return

        log_data(logger, WARNING, f"Agent exceeded max_iterations={self.max_iterations}")
        raise MaxIterationsError(f"Agent exceeded {self.max_iterations} iterations")

    async def run(
        self,
        prompt: str | list[Message],
        *,
        context: dict[str, Any] | None = None,
        response_model: type[BaseModel] | None = None,
    ) -> Stream:
        """Execute the agent with the given prompt."""
        if isinstance(prompt, str):
            mgs: list[Message] = []
            composed = self._build_system_prompt()
            if composed:
                mgs.append(Message.system(composed))
            mgs.append(Message.user(prompt))
        else:
            mgs = list(prompt)

        ctx = context or {}
        if response_model is not None:
            ctx["_response_model"] = response_model

        log_data(logger, INFO, "Agent.run() called",
                 data={"input_length": len(prompt) if isinstance(prompt, str) else len(prompt),
                       "has_system": self.system_prompt is not None,
                       "has_skills": len(self.skills) > 0,
                       "tools": len(self._all_tools()),
                       "response_model": response_model.__name__ if response_model else None})

        tracker = StateTracker()

        async def _handler(msgs: list[Message], c: dict[str, Any]) -> AsyncIterator[StreamEvent]:
            async for event in self._run_loop(msgs, c, tracker=tracker):
                yield event

        if self.middlewares:
            chain = MiddlewareChain(self.middlewares)
            return Stream(chain.run(mgs, ctx, _handler), response_model=response_model)

        return Stream(_handler(mgs, ctx), response_model=response_model)

# Resolve forward reference for Skill via model_rebuild
