"""ReAct agent — Thought/Action/Observation loop with explicit reasoning."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field

from chainforge.core.agent import Agent
from chainforge.core.errors import MaxIterationsError
from chainforge.core.llm import LLM
from chainforge.core.message import Message
from chainforge.core.stream import EventType, Stream, StreamEvent
from chainforge.core.tool import Tool


REACT_SYSTEM_PROMPT = """You are a helpful assistant that uses a structured reasoning process.

You operate in a Thought/Action/Observation loop:

1. **Thought**: Reason about the current situation and what needs to be done.
2. **Action**: Use one of the available tools to gather information or take action.
3. **Observation**: Review the result and decide next steps.

Continue this loop until you have enough information to provide a complete answer.
When you're done, provide your final answer without any tool calls.
"""


class ReActAgent(BaseModel):
    """ReAct agent with explicit reasoning steps.

    Extends the base Agent with a dedicated reasoning system prompt
    and optional step-by-step logging.
    """

    llm: LLM = Field(description="LLM provider")
    tools: list[Tool] = Field(default_factory=list, description="Available tools")
    max_iterations: int = Field(default=15, description="Max reasoning iterations")
    verbose: bool = Field(default=False, description="Print reasoning steps")
    temperature: float | None = Field(default=None)
    max_tokens: int | None = Field(default=None)

    class Config:
        arbitrary_types_allowed = True

    async def run(
        self,
        prompt: str | list[Message],
        *,
        context: dict[str, Any] | None = None,
    ) -> Stream:
        """Run the ReAct agent with reasoning loop."""

        # Wrap with system prompt if using a string prompt
        if isinstance(prompt, str):
            messages = [
                Message.system(REACT_SYSTEM_PROMPT),
                Message.user(prompt),
            ]
        else:
            messages = list(prompt)

        agent = Agent(
            llm=self.llm,
            tools=self.tools,
            system_prompt=None,  # We already injected it above
            max_iterations=self.max_iterations,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        return await agent.run(messages, context=context)
