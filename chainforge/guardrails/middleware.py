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
"""Guardrail middleware — integrate guardrails into the Agent middleware chain."""

from __future__ import annotations

from typing import Any

from chainforge.core.message import Message, Role
from chainforge.guardrails.base import Guardrail, GuardrailAction, GuardrailResult
from chainforge.logging import get_logger

logger = get_logger("guardrails.middleware")


class GuardrailMiddleware:
    """Runs guardrails on agent input and output.

    Wraps a list of guardrails into ChainForge's agent pipeline.
    Runs input guardrails on user messages before sending to the LLM,
    and output guardrails on agent responses before delivering.

    Usage:
        from chainforge.guardrails.input import InjectionDetector
        from chainforge.guardrails.output import PIILeakGuard
        from chainforge.guardrails.middleware import GuardrailMiddleware

        agent = Agent(
            llm=llm,
            middlewares=[GuardrailMiddleware(guardrails=[
                ("input", InjectionDetector()),
                ("output", PIILeakGuard()),
            ])],
        )
    """

    def __init__(
        self,
        guardrails: list[tuple[str, Guardrail]] | None = None,
        *,
        fail_open: bool = False,
        on_block: str = "raise",
    ):
        """Initialize the guardrail middleware.

        Args:
            guardrails: List of (phase, guardrail) tuples where phase is
                       "input" (user → LLM) or "output" (LLM → user).
            fail_open: If True, allow requests when guardrail check errors.
                       If False, block on errors.
            on_block: What to do when blocked: "raise" exception or "return" error message.
        """
        self._guardrails = guardrails or []
        self.fail_open = fail_open
        self.on_block = on_block

    def add_input_guardrail(self, guardrail: Guardrail) -> None:
        """Add an input guardrail (runs on user messages)."""
        self._guardrails.append(("input", guardrail))

    def add_output_guardrail(self, guardrail: Guardrail) -> None:
        """Add an output guardrail (runs on agent responses)."""
        self._guardrails.append(("output", guardrail))

    async def before_llm(self, messages: list[Message], context: dict[str, Any] | None = None) -> list[Message]:
        """Run input guardrails on the last user message."""
        if not messages:
            return messages

        last_msg = messages[-1]
        if last_msg.role != Role.user or not last_msg.content:
            return messages

        context = context or {}

        for phase, guardrail in self._guardrails:
            if phase != "input":
                continue

            try:
                result = await guardrail.check(str(last_msg.content), context=context)
                if not result.passed:
                    logger.warning(f"Input guardrail blocked: {result.reason}")
                    return self._handle_block(result, messages)
            except Exception as e:
                logger.error(f"Input guardrail error: {e}")
                if not self.fail_open:
                    return self._handle_error(e, messages)

        return messages

    async def after_llm(self, response_text: str, context: dict[str, Any] | None = None) -> str:
        """Run output guardrails on the LLM response."""
        if not response_text:
            return response_text

        context = context or {}

        for phase, guardrail in self._guardrails:
            if phase != "output":
                continue

            try:
                result = await guardrail.check(response_text, context=context)
                if not result.passed:
                    logger.warning(f"Output guardrail blocked: {result.reason}")
                    if self.on_block == "raise":
                        raise GuardrailBlocked(result)
                    return f"[Content blocked by safety filter: {result.reason}]"
            except GuardrailBlocked:
                raise
            except Exception as e:
                logger.error(f"Output guardrail error: {e}")
                if not self.fail_open:
                    if self.on_block == "raise":
                        raise GuardrailBlocked(
                            GuardrailResult(passed=False, reason=f"Guardrail error: {e}")
                        )
                    return f"[Guardrail error: content blocked]"

        return response_text

    def _handle_block(self, result: GuardrailResult, messages: list[Message]) -> list[Message]:
        """Handle a blocked message."""
        if self.on_block == "raise":
            raise GuardrailBlocked(result)
        # Replace the last message with a blocked notice
        messages = list(messages)
        messages[-1] = Message(
            role=Role.user,
            content=f"[Input blocked: {result.reason}]",
        )
        return messages

    def _handle_error(self, error: Exception, messages: list[Message]) -> list[Message]:
        """Handle a guardrail error."""
        if self.on_block == "raise":
            raise GuardrailBlocked(
                GuardrailResult(passed=False, reason=f"Guardrail error: {error}")
            )
        messages = list(messages)
        messages[-1] = Message(
            role=Role.user,
            content=f"[Input blocked due to guardrail error]",
        )
        return messages


class GuardrailBlocked(Exception):
    """Raised when a guardrail blocks a request."""

    def __init__(self, result: GuardrailResult):
        self.result = result
        super().__init__(result.reason)
