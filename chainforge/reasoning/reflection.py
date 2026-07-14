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
"""Reflection reasoning — self-critique and improvement."""

from __future__ import annotations

from typing import Any

from chainforge.core.message import Message, Role
from chainforge.reasoning.base import ReasoningStrategy


class SelfReflection(ReasoningStrategy):
    """After generating a response, asks the LLM to self-critique and improve.

    This produces better quality outputs by adding a reflection step
    where the LLM reviews its own answer and refines it.

    Usage:
        from chainforge.reasoning import SelfReflection

        agent = Agent(
            llm=llm,
            reasoning=[SelfReflection()],
        )
    """

    name: str = "self_reflection"
    critique_prompt: str = (
        "Review your previous response carefully. "
        "Identify any errors, omissions, or areas for improvement. "
        "Then provide a revised, improved version."
    )

    def __init__(self, critique_prompt: str | None = None, max_reflections: int = 1):
        if critique_prompt:
            self.critique_prompt = critique_prompt
        self.max_reflections = max_reflections
        self._reflection_count = 0

    async def after_llm(
        self,
        response: Any,
        messages: list,
        context: dict[str, Any] | None = None,
    ) -> tuple[Any, list, dict[str, Any] | None]:
        """After the LLM responds, add a critique prompt for the next iteration.

        This only triggers when the response has text content and
        we haven't exceeded max_reflections.
        """
        if not response or not response.content:
            return response, messages, context

        # Don't reflect on tool call responses
        if response.tool_calls:
            return response, messages, context

        if self._reflection_count >= self.max_reflections:
            return response, messages, context

        self._reflection_count += 1

        # Store the original response in context and add critique request
        messages = list(messages)
        messages.append(Message(role=Role.assistant, content=response.content))
        messages.append(Message(role=Role.system, content=self.critique_prompt))

        return response, messages, context

    async def should_stop(
        self,
        messages: list,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """Stop when we've done enough reflections."""
        return self._reflection_count >= self.max_reflections


class Verification(ReasoningStrategy):
    """Asks the LLM to verify its answer before finalizing.

    After the initial response, prompts the LLM to verify and
    correct any mistakes, similar to a "double-check" step.

    Usage:
        from chainforge.reasoning import Verification

        agent = Agent(
            llm=llm,
            reasoning=[Verification()],
        )
    """

    name: str = "verification"
    verify_prompt: str = (
        "Verify the above answer. Check for factual accuracy, "
        "logical consistency, and completeness. "
        "If you find any issues, provide a corrected version."
    )

    def __init__(self, verify_prompt: str | None = None):
        if verify_prompt:
            self.verify_prompt = verify_prompt
        self._verified = False

    async def after_llm(
        self,
        response: Any,
        messages: list,
        context: dict[str, Any] | None = None,
    ) -> tuple[Any, list, dict[str, Any] | None]:
        """After initial response, add verification request."""
        if self._verified or not response or not response.content:
            return response, messages, context
        if response.tool_calls:
            return response, messages, context

        self._verified = True
        messages = list(messages)
        messages.append(Message(role=Role.assistant, content=response.content))
        messages.append(Message(role=Role.system, content=self.verify_prompt))
        # Return empty content so the loop continues for verification
        response.content = None
        return response, messages, context

    async def should_stop(
        self,
        messages: list,
        context: dict[str, Any] | None = None,
    ) -> bool:
        return self._verified
