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
"""SelfAsk Agent — 分解 → 回答 → 综合。"""

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
from chainforge.core.structured_output import parse_structured_response, model_to_json_schema
from chainforge.core.tool import Tool
from chainforge.logging import get_logger, log_data

logger = get_logger("agents.self_ask")


class DecomposeSchema(BaseModel):
    """Schema for question decomposition."""
    sub_questions: list[str] = Field(description="List of sub-questions to answer")


_DECOMPOSE_SCHEMA = model_to_json_schema(DecomposeSchema)

DECOMPOSE_PROMPT = f"""Break the user's question into 2-5 specific, answerable sub-questions.

Respond in JSON that matches this schema:
{json.dumps(_DECOMPOSE_SCHEMA, indent=2)}"""


class SelfAsk(BaseModel):
    """Agent that decomposes questions, answers each, then synthesizes."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    llm: LLM = Field(description="LLM provider")
    tools: list[Tool] = Field(default_factory=list, description="Available tools")
    max_sub_questions: int = Field(default=5, description="Max sub-questions")
    max_iterations: int = Field(default=5, description="Max iterations per sub-question")
    temperature: float | None = Field(default=None)

    async def run(self, prompt: str | list[Message], *, context: dict[str, Any] | None = None) -> Stream:
        async def _generate() -> AsyncIterator[StreamEvent]:
            user_prompt = prompt if isinstance(prompt, str) else (prompt[-1].content if prompt[-1].content else "")
            log_data(logger, INFO, "SelfAsk started")

            # Phase 1: Decompose
            yield StreamEvent(type=EventType.state, content="decomposing", data={"state": "decomposing"})
            yield StreamEvent(type=EventType.status, content="Breaking down the question...")

            resp = await self.llm.generate([Message.system(DECOMPOSE_PROMPT), Message.user(user_prompt)])
            text = resp.content or ""

            # Parse using Pydantic model
            sub_questions = []
            try:
                parsed = parse_structured_response(text, DecomposeSchema)
                sub_questions = parsed.sub_questions
            except Exception:
                pass

            if not sub_questions:
                for line in text.split("\n"):
                    mm = re.match(r'^\s*\d+[\.\)]\s*(.*)', line)
                    if mm and "?" in mm.group(1):
                        sub_questions.append(mm.group(1))

            sub_questions = sub_questions[:self.max_sub_questions]
            log_data(logger, INFO, f"Decomposed into {len(sub_questions)} sub-questions")
            yield StreamEvent(type=EventType.text, content=f"[Sub-questions]\n" + "\n".join(f"  Q{i+1}: {q}" for i, q in enumerate(sub_questions)) + "\n")

            # Phase 2: Answer each
            yield StreamEvent(type=EventType.state, content="answering", data={"state": "answering"})
            sub_answers = []
            for i, sq in enumerate(sub_questions):
                yield StreamEvent(type=EventType.status, content=f"Answering Q{i+1}/{len(sub_questions)}")
                a_agent = Agent(llm=self.llm, tools=self.tools,
                                system_prompt=f"Answering sub-question {i+1}/{len(sub_questions)}",
                                max_iterations=self.max_iterations, temperature=self.temperature)
                a_stream = await a_agent.run(f"Answer: {sq}\nContext: {user_prompt}", context=context)
                parts = []
                async for ev in a_stream:
                    if ev.type == EventType.text and ev.content:
                        parts.append(ev.content)
                    yield ev
                sub_answers.append(f"Q{i+1}: {sq}\nA: {''.join(parts)}")

            # Phase 3: Synthesize
            yield StreamEvent(type=EventType.state, content="synthesizing", data={"state": "synthesizing"})
            yield StreamEvent(type=EventType.status, content="Synthesizing final answer...")
            final = await self.llm.generate([Message.user(
                f"Original question: {user_prompt}\n\nSub-answers:\n{chr(10).join(sub_answers)}\n\nProvide a comprehensive final answer.")])
            if final.content:
                yield StreamEvent(type=EventType.text, content=final.content)
            yield StreamEvent(type=EventType.state, content="done", data={"state": "done"})
            yield StreamEvent(type=EventType.done)

        return Stream(_generate())
