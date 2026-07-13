"""PlanAndExecute — 先规划，再逐步执行。"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from logging import DEBUG, INFO
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from chainforge.core.agent import Agent
from chainforge.core.llm import LLM
from chainforge.core.message import Message
from chainforge.core.stream import EventType, Stream, StreamEvent
from chainforge.core.tool import Tool
from chainforge.logging import get_logger, log_data

logger = get_logger("agents.plan_execute")

PLAN_PROMPT = """You are a planning agent. Create a step-by-step plan to accomplish the task.
Available tools: {tool_descriptions}

Respond in JSON format:
{{
  "thought": "Your reasoning",
  "steps": [
    {{"step": 1, "description": "...", "tool": "tool_name_or_none"}}
  ]
}}
"""

SYNTHESIS_PROMPT = """You completed these steps:
{step_results}

Synthesize into a final answer for: {original_request}
"""


class PlanAndExecute(BaseModel):
    """Agent that plans before executing."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    llm: LLM = Field(description="LLM provider")
    tools: list[Tool] = Field(default_factory=list, description="Available tools")
    max_plan_steps: int = Field(default=7, description="Max plan steps")
    max_iterations: int = Field(default=5, description="Max iterations per step")
    temperature: float | None = Field(default=None)

    async def run(self, prompt: str | list[Message], *, context: dict[str, Any] | None = None) -> Stream:
        async def _generate() -> AsyncIterator[StreamEvent]:
            user_prompt = prompt if isinstance(prompt, str) else (prompt[-1].content if prompt[-1].content else "")
            log_data(logger, INFO, "PlanAndExecute started", data={"tools": [t.spec.name for t in self.tools]})

            # Phase 1: Plan
            yield StreamEvent(type=EventType.state, content="planning", data={"state": "planning", "phase": "plan"})
            yield StreamEvent(type=EventType.status, content="Creating plan...")

            tool_desc = "\n".join(f"  - {t.spec.name}: {t.spec.description}" for t in self.tools) if self.tools else "  (none)"
            plan_resp = await self.llm.generate([
                Message.system(PLAN_PROMPT.format(tool_descriptions=tool_desc)),
                Message.user(user_prompt),
            ])
            plan_text = plan_resp.content or ""
            yield StreamEvent(type=EventType.text, content=f"[Plan]\n{plan_text}\n")
            log_data(logger, INFO, "Plan created", data={"plan_length": len(plan_text)})

            # Parse steps
            steps = []
            m = re.search(r'"steps"\s*:\s*\[(.*?)\]', plan_text, re.DOTALL)
            if m:
                try:
                    data = json.loads("{" + m.string[m.start()-1:m.end()+1] if m.string[m.start()-1] == "{" else "{}")
                    steps = data.get("steps", [])
                except (json.JSONDecodeError, AttributeError):
                    pass
            if not steps:
                for line in plan_text.split("\n"):
                    mm = re.match(r'^\s*(?:Step\s+)?(\d+)[\.:\)]\s*(.*)', line)
                    if mm:
                        steps.append({"step": int(mm.group(1)), "description": mm.group(2), "tool": None})

            log_data(logger, INFO, f"Extracted {len(steps)} steps")

            # Phase 2: Execute
            yield StreamEvent(type=EventType.state, content="executing", data={"state": "executing", "phase": "execute"})
            step_results = []
            for i, step in enumerate(steps):
                desc = step.get("description", f"Step {i + 1}")
                yield StreamEvent(type=EventType.status, content=f"Step {i + 1}/{len(steps)}: {desc}")
                step_agent = Agent(llm=self.llm, tools=self.tools,
                                   system_prompt=f"Executing step {i + 1}/{len(steps)}: {desc}",
                                   max_iterations=self.max_iterations, temperature=self.temperature)
                s_stream = await step_agent.run(f"Execute: {desc}\nContext: {user_prompt}", context=context)
                parts = []
                async for ev in s_stream:
                    if ev.type == EventType.text and ev.content:
                        parts.append(ev.content)
                    if ev.type != EventType.done:
                        yield ev
                step_results.append(f"Step {i + 1}: {desc}\nResult: {''.join(parts)}")

            # Phase 3: Synthesize
            yield StreamEvent(type=EventType.state, content="synthesizing", data={"state": "synthesizing", "phase": "synthesize"})
            yield StreamEvent(type=EventType.status, content="Synthesizing results...")
            synth = await self.llm.generate([Message.system(SYNTHESIS_PROMPT.format(
                step_results="\n\n".join(step_results), original_request=user_prompt))])
            if synth.content:
                yield StreamEvent(type=EventType.text, content=synth.content)
            yield StreamEvent(type=EventType.state, content="done", data={"state": "done", "steps": len(steps)})
            yield StreamEvent(type=EventType.done)

        return Stream(_generate())
