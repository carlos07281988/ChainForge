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
"""Reflection Agent — 生成 → 自省 → 改进。"""

from __future__ import annotations

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

logger = get_logger("agents.reflection")

CRITIQUE_PROMPT = """Critique the following answer to: {question}

Answer:
{answer}

Provide specific, actionable feedback on:
1. Accuracy — any factual issues?
2. Completeness — what's missing?
3. Clarity — how can it be improved?"""

IMPROVE_PROMPT = """Original question: {question}

Previous answer:
{answer}

Your critique:
{critique}

Provide an improved answer addressing all critique points. Keep the good, fix the issues."""


class Reflection(BaseModel):
    """Agent that reflects on and improves its output."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    llm: LLM = Field(description="LLM provider")
    tools: list[Tool] = Field(default_factory=list, description="Available tools")
    reflection_rounds: int = Field(default=1, description="Number of reflection cycles")
    max_iterations: int = Field(default=8, description="Max iterations per Agent call")
    temperature: float | None = Field(default=None)

    async def run(self, prompt: str | list[Message], *, context: dict[str, Any] | None = None) -> Stream:
        async def _generate() -> AsyncIterator[StreamEvent]:
            user_prompt = prompt if isinstance(prompt, str) else (prompt[-1].content if prompt[-1].content else "")
            log_data(logger, INFO, f"Reflection started (rounds={self.reflection_rounds})")

            # Phase 1: Generate initial answer
            yield StreamEvent(type=EventType.state, content="generating", data={"state": "generating", "round": 0})
            yield StreamEvent(type=EventType.status, content="Generating initial answer...")

            gen_agent = Agent(llm=self.llm, tools=self.tools, max_iterations=self.max_iterations, temperature=self.temperature)
            gen_stream = await gen_agent.run(prompt, context=context)
            text_parts = []
            async for ev in gen_stream:
                if ev.type == EventType.text and ev.content:
                    text_parts.append(ev.content)
                yield ev
            current_answer = "".join(text_parts)

            for round_idx in range(1, self.reflection_rounds + 1):
                # Phase 2: Critique
                yield StreamEvent(type=EventType.state, content="critiquing", data={"state": "critiquing", "round": round_idx})
                yield StreamEvent(type=EventType.status, content=f"Critiquing (round {round_idx}/{self.reflection_rounds})...")

                crit = await self.llm.generate([Message.user(CRITIQUE_PROMPT.format(
                    question=user_prompt, answer=current_answer))])
                critique = crit.content or ""
                yield StreamEvent(type=EventType.text, content=f"\n[Critique {round_idx}]\n{critique}\n")
                log_data(logger, DEBUG, f"Critique round {round_idx} done", data={"round": round_idx, "length": len(critique)})

                # Phase 3: Improve
                yield StreamEvent(type=EventType.state, content="improving", data={"state": "improving", "round": round_idx})
                yield StreamEvent(type=EventType.status, content=f"Improving (round {round_idx}/{self.reflection_rounds})...")

                impr = await self.llm.generate([Message.user(IMPROVE_PROMPT.format(
                    question=user_prompt, answer=current_answer, critique=critique))])
                if impr.content:
                    yield StreamEvent(type=EventType.text, content=f"\n[Improved {round_idx}]\n{impr.content}\n")
                    current_answer = impr.content

            yield StreamEvent(type=EventType.state, content="done", data={"state": "done", "rounds": self.reflection_rounds + 1})
            yield StreamEvent(type=EventType.done)
            log_data(logger, INFO, f"Reflection done ({self.reflection_rounds + 1} rounds)")

        return Stream(_generate())
