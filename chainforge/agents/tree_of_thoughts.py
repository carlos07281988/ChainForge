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
"""TreeOfThoughts — 多路径推理，BFS 搜索最佳答案路径。

对复杂推理任务同时探索多条推理路径，每步评估候选并保留最优分支。
适用于数学推理、逻辑分析、策略规划等需要穷举可能的场景。
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from logging import DEBUG, INFO
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from chainforge.core.llm import LLM
from chainforge.core.message import Message
from chainforge.core.stream import EventType, Stream, StreamEvent
from chainforge.core.tool import Tool
from chainforge.logging import get_logger, log_data

logger = get_logger("agents.tree_of_thoughts")

THINK_PROMPT = """You are exploring reasoning paths for a problem.

Problem: {problem}

Current context so far:
{context}

Generate {num_candidates} distinct, plausible next steps or sub-thoughts.
Each should advance the reasoning toward a solution.
Label them A, B, C...

Respond with numbered options."""
EVALUATE_PROMPT = """Evaluate the following reasoning step for: {problem}

Step: {step}

Rate it 1-10 on:
1. Promise — how likely to lead to a correct solution
2. Coherence — how logically sound
3. Progress — how much it advances understanding

Respond with just a number 1-10."""


class TreeOfThoughts(BaseModel):
    """Agent that explores multiple reasoning paths via BFS.

    Usage:
        agent = TreeOfThoughts(
            llm=OpenAIProvider(model="gpt-4o"),
            tools=[calculator],
            candidates_per_step=3,
            breadth=2,
            depth=3,
        )
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    llm: LLM = Field(description="LLM provider")
    tools: list[Tool] = Field(default_factory=list, description="Available tools")
    candidates_per_step: int = Field(default=3, description="Thoughts to generate per node")
    breadth: int = Field(default=2, description="Top-K branches to keep per depth")
    depth: int = Field(default=3, description="Max reasoning depth")
    temperature: float | None = Field(default=0.7)

    async def run(self, prompt: str | list[Message], *, context: dict[str, Any] | None = None) -> Stream:
        async def _generate() -> AsyncIterator[StreamEvent]:
            user_prompt = prompt if isinstance(prompt, str) else (prompt[-1].content if prompt[-1].content else "")
            log_data(logger, INFO, "TreeOfThoughts started",
                     data={"candidates": self.candidates_per_step, "breadth": self.breadth, "depth": self.depth})

            yield StreamEvent(type=EventType.state, content="initializing",
                              data={"state": "initializing", "strategy": "bfs"})
            yield StreamEvent(type=EventType.status,
                              content=f"Exploring {self.depth} depth × {self.breadth} breadth reasoning tree...")

            # BFS tree: each level is a list of (path_so_far, score)
            tree = [[(user_prompt, 10)]]  # root
            best_path = None
            best_score = -1

            for d in range(self.depth):
                yield StreamEvent(type=EventType.state, content="exploring",
                                  data={"state": "exploring", "depth": d + 1, "total": self.depth})
                yield StreamEvent(type=EventType.status,
                                  content=f"Depth {d + 1}/{self.depth}: branching...")

                current_level = tree[-1]
                next_candidates = []

                for path_text, parent_score in current_level:
                    # Generate N thoughts from this node
                    think_msgs = [
                        Message.system(THINK_PROMPT.format(
                            problem=user_prompt, context=path_text,
                            num_candidates=self.candidates_per_step)),
                        Message.user(f"Generate {self.candidates_per_step} next steps."),
                    ]
                    resp = await self.llm.generate(think_msgs)
                    thoughts = self._extract_thoughts(resp.content or "", self.candidates_per_step)

                    for thought in thoughts:
                        # Evaluate this thought
                        eval_msgs = [Message.system(EVALUATE_PROMPT.format(problem=user_prompt, step=thought))]
                        eval_resp = await self.llm.generate(eval_msgs)
                        score = self._extract_score(eval_resp.content or "")

                        new_path = f"{path_text}\n→ {thought}"
                        next_candidates.append((new_path, score))

                        yield StreamEvent(type=EventType.text,
                                          content=f"  [d={d + 1}] score={score:.1f} | {thought[:80]}...\n")
                        log_data(logger, DEBUG, f"Candidate scored", data={"depth": d + 1, "score": score, "thought": thought[:60]})

                # Keep top K from this level
                next_candidates.sort(key=lambda x: x[1], reverse=True)
                top_k = next_candidates[:self.breadth]

                yield StreamEvent(type=EventType.status,
                                  content=f"Depth {d + 1}: kept top {len(top_k)}/{len(next_candidates)} candidates (best={top_k[0][1]:.1f})")

                # Track best path
                for p, s in top_k:
                    if s > best_score:
                        best_score = s
                        best_path = p

                tree.append(top_k)

                if not top_k:
                    break

            # Output best path
            yield StreamEvent(type=EventType.state, content="selecting",
                              data={"state": "selecting", "best_score": best_score})
            yield StreamEvent(type=EventType.status, content="Selecting best reasoning path...")

            summary = [
                f"[Tree of Thoughts — Best Path (score={best_score:.1f})]",
                "",
                best_path or user_prompt,
            ]
            result = "\n".join(summary)
            yield StreamEvent(type=EventType.text, content=result)

            # Optional: final refinement with tools
            if self.tools:
                yield StreamEvent(type=EventType.status, content="Refining with tools...")
                from chainforge.core.agent import Agent
                refiner = Agent(llm=self.llm, tools=self.tools, max_iterations=3,
                                temperature=self.temperature)
                ref_stream = await refiner.run(
                    f"Based on this reasoning, provide the final answer:\n\n{result}",
                    context=context)
                async for ev in ref_stream:
                    if ev.type != EventType.done:
                        yield ev

            yield StreamEvent(type=EventType.state, content="done",
                              data={"state": "done", "depth": self.depth, "candidates_explored": len(tree) * self.candidates_per_step})
            yield StreamEvent(type=EventType.done)

            log_data(logger, INFO, f"TreeOfThoughts done (best={best_score:.1f})",
                     data={"best_score": best_score, "depth": self.depth})

        return Stream(_generate())

    def _extract_thoughts(self, text: str, n: int) -> list[str]:
        """Extract numbered/lettered thought candidates from LLM output."""
        thoughts = []
        # Try numbered list
        for line in text.split("\n"):
            m = re.match(r'^\s*(?:\d+|[A-Z])[\.\):]\s*(.*)', line)
            if m:
                t = m.group(1).strip()
                if len(t) > 10:  # Minimum substance
                    thoughts.append(t)
            if len(thoughts) >= n:
                break
        return thoughts[:n] if thoughts else [f"Continue exploring... (option {i})" for i in range(n)]

    def _extract_score(self, text: str) -> float:
        """Extract a numeric score from evaluator output."""
        # Look for a number 1-10
        nums = re.findall(r'\b([1-9]|10)\b', text)
        if nums:
            return float(nums[0])
        return 5.0
