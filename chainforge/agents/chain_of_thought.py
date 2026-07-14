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
"""ChainOfThought — 结构化推理 + Self-Consistency（多路径集成）。

生成 N 条独立推理路径，分别使用工具，然后通过投票/对比聚合出最优答案。
适用于需要高可靠性的推理、数学、事实核查等场景。
"""

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

logger = get_logger("agents.chain_of_thought")

COT_PROMPT = """Let's approach this step by step.

{question}

Think carefully, show your reasoning, and reach a conclusion."""
AGGREGATE_PROMPT = """Multiple reasoning paths were used to answer this question.

Question: {question}

Reasoning paths:
{paths}

Analyze these paths, identify common conclusions and contradictions.
Provide the most reliable final answer based on consensus."""


class ChainOfThought(BaseModel):
    """Agent with structured reasoning + optional self-consistency (ensemble).

    Usage:
        agent = ChainOfThought(
            llm=OpenAIProvider(model="gpt-4o"),
            tools=[calculator],
            num_paths=3,      # 3 independent CoT paths
            aggregate="vote", # or "compare"
        )
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    llm: LLM = Field(description="LLM provider")
    tools: list[Tool] = Field(default_factory=list, description="Available tools")
    num_paths: int = Field(default=3, description="Number of independent CoT paths (1 = no ensemble)")
    aggregate: str = Field(default="vote", description="'vote' = consensus, 'compare' = best-of-N")
    temperature: float | None = Field(default=0.5)
    max_iterations: int = Field(default=6)

    async def run(self, prompt: str | list[Message], *, context: dict[str, Any] | None = None) -> Stream:
        async def _generate() -> AsyncIterator[StreamEvent]:
            user_prompt = prompt if isinstance(prompt, str) else (prompt[-1].content if prompt[-1].content else "")
            log_data(logger, INFO, f"ChainOfThought started (paths={self.num_paths})", data={"num_paths": self.num_paths})

            yield StreamEvent(type=EventType.state, content="reasoning",
                              data={"state": "reasoning", "num_paths": self.num_paths})
            yield StreamEvent(type=EventType.status,
                              content=f"Generating {self.num_paths} independent reasoning paths...")

            # Generate N independent CoT paths
            paths = []
            for i in range(self.num_paths):
                yield StreamEvent(type=EventType.state, content="reasoning",
                                  data={"state": "reasoning", "path": i + 1, "total": self.num_paths})
                yield StreamEvent(type=EventType.status,
                                  content=f"Path {i + 1}/{self.num_paths}...")

                path_agent = Agent(
                    llm=self.llm,
                    tools=self.tools,
                    system_prompt=f"You are reasoning path {i + 1}/{self.num_paths}. Be thorough and independent.",
                    max_iterations=self.max_iterations,
                    temperature=self.temperature + 0.1 * i,  # Diverse temperatures
                )
                path_stream = await path_agent.run(
                    COT_PROMPT.format(question=user_prompt),
                    context=context,
                )
                parts = []
                async for ev in path_stream:
                    if ev.type == EventType.text and ev.content:
                        parts.append(ev.content)
                    if ev.type != EventType.done:
                        yield ev

                path_text = "".join(parts)
                paths.append(f"=== Path {i + 1} ===\n{path_text}")
                log_data(logger, DEBUG, f"Path {i + 1} done", data={"path": i + 1, "length": len(path_text)})

            # Aggregate if multiple paths
            if self.num_paths > 1:
                yield StreamEvent(type=EventType.state, content="aggregating",
                                  data={"state": "aggregating", "method": self.aggregate})
                yield StreamEvent(type=EventType.status,
                                  content=f"Aggregating {self.num_paths} paths via '{self.aggregate}'...")

                agg_msgs = [Message.user(AGGREGATE_PROMPT.format(
                    question=user_prompt, paths="\n\n".join(paths)))]
                agg_resp = await self.llm.generate(agg_msgs)
                if agg_resp.content:
                    yield StreamEvent(type=EventType.text,
                                      content=f"\n[Consensus]\n{agg_resp.content}\n")
            else:
                # Single path: just note the reasoning
                yield StreamEvent(type=EventType.status, content="Single path (no aggregation needed)")

            yield StreamEvent(type=EventType.state, content="done",
                              data={"state": "done", "paths": self.num_paths})
            yield StreamEvent(type=EventType.done)
            log_data(logger, INFO, f"ChainOfThought done ({self.num_paths} paths)")

        return Stream(_generate())
