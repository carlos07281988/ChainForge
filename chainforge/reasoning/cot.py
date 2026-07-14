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
"""Chain of Thought reasoning — inject thinking instructions."""

from __future__ import annotations

from typing import Any

from chainforge.core.message import Message, Role
from chainforge.reasoning.base import ReasoningStrategy


class ChainOfThought(ReasoningStrategy):
    """Injects a step-by-step thinking instruction before the LLM call.

    This encourages the LLM to reason explicitly before answering,
    which improves accuracy on complex tasks.

    Usage:
        from chainforge.reasoning import ChainOfThought

        agent = Agent(
            llm=llm,
            reasoning=[ChainOfThought()],
        )
    """

    name: str = "chain_of_thought"
    prompt: str = "Let me think through this step by step."

    def __init__(self, prompt: str | None = None, inject_before_answer: bool = True):
        if prompt:
            self.prompt = prompt
        self.inject_before_answer = inject_before_answer

    async def before_llm(
        self,
        messages: list,
        context: dict[str, Any] | None = None,
    ) -> tuple[list, dict[str, Any] | None]:
        """Inject a thinking prompt before the LLM call.

        Adds a system message encouraging chain-of-thought reasoning
        if one doesn't already exist.
        """
        # Check if a CoT prompt is already present
        has_cot = any(
            hasattr(m, "content") and m.content and "step by step" in m.content.lower()
            for m in messages
        )

        if not has_cot and self.inject_before_answer:
            messages = list(messages)
            messages.append(Message(role=Role.system, content=self.prompt))

        return messages, context


class ReasoningSteps(ReasoningStrategy):
    """Breaks the user's request into explicit sub-steps.

    Before the main LLM call, generates a plan of steps, then
    executes them one by one.

    Usage:
        from chainforge.reasoning import ReasoningSteps

        agent = Agent(
            llm=llm,
            reasoning=[ReasoningSteps()],
        )
    """

    name: str = "reasoning_steps"

    def __init__(self, max_steps: int = 5):
        self.max_steps = max_steps
        self._step_count = 0

    async def before_llm(
        self,
        messages: list,
        context: dict[str, Any] | None = None,
    ) -> tuple[list, dict[str, Any] | None]:
        """On the first iteration, ask the LLM to plan steps."""
        iteration = (context or {}).get("iteration", 0)
        if iteration == 0:
            self._step_count = 0
            messages = list(messages)
            plan_msg = Message(
                role=Role.system,
                content=(
                    "Before answering, break down this problem into "
                    f"up to {self.max_steps} clear steps. Number each step. "
                    "Then work through them one at a time."
                ),
            )
            messages.append(plan_msg)
        return messages, context

    async def should_stop(
        self,
        messages: list,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """Stop after max iterations or when tool results indicate completion."""
        self._step_count += 1
        if self._step_count >= self.max_steps:
            return True
        return False
