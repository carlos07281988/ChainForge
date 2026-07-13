"""RouterAgent — 意图分类 → 路由到专业子 Agent。

通过分类器识别用户意图，将任务分派给最适合的子 Agent。
每个子 Agent 可以有不同的 LLM、tools 和 system_prompt。
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
from chainforge.logging import get_logger, log_data

logger = get_logger("agents.router")

CLASSIFY_PROMPT = """Classify the following user request into exactly one category.

Categories: {categories}

Request: {request}

Respond with just the category name, nothing else."""


class RouterAgent(BaseModel):
    """Agent that classifies intent and routes to specialized sub-agents.

    Usage:
        router = RouterAgent(
            classifier_llm=OpenAIProvider(model="gpt-4o-mini"),
            routes={
                "weather": weather_agent,
                "search": search_agent,
                "coding": code_agent,
            },
            default_route="search",
        )
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    classifier_llm: LLM = Field(description="LLM used for intent classification")
    routes: dict[str, Any] = Field(default_factory=dict, description="Route name → Agent")
    default_route: str = Field(default="", description="Fallback route if classification fails")
    unknown_agent: Any | None = Field(default=None, description="Agent for unclassified requests")

    async def run(self, prompt: str | list[Message], *, context: dict[str, Any] | None = None) -> Stream:
        async def _generate() -> AsyncIterator[StreamEvent]:
            user_prompt = prompt if isinstance(prompt, str) else (prompt[-1].content if prompt[-1].content else "")
            log_data(logger, INFO, "RouterAgent started", data={"routes": list(self.routes.keys())})

            # Phase 1: Classify
            yield StreamEvent(type=EventType.state, content="classifying",
                              data={"state": "classifying"})
            yield StreamEvent(type=EventType.status, content="Classifying intent...")

            categories = ", ".join(self.routes.keys())
            classify_msgs = [Message.user(CLASSIFY_PROMPT.format(
                categories=categories, request=user_prompt))]
            classify_resp = await self.classifier_llm.generate(classify_msgs)
            predicted = (classify_resp.content or "").strip().lower()

            # Find matching route
            selected = None
            for route_name in self.routes:
                if route_name.lower() in predicted:
                    selected = route_name
                    break

            if not selected:
                selected = self.default_route if self.default_route in self.routes else None

            if not selected or selected not in self.routes:
                # No route found
                yield StreamEvent(type=EventType.error,
                                  content=f"Could not classify request into known routes: {categories}")
                yield StreamEvent(type=EventType.done)
                return

            yield StreamEvent(type=EventType.state, content=f"routing",
                              data={"state": "routing", "route": selected, "confidence": predicted})
            yield StreamEvent(type=EventType.status,
                              content=f"Routed to: {selected}")

            log_data(logger, INFO, f"Routed to '{selected}'", data={"route": selected, "predicted": predicted})

            # Phase 2: Execute
            target_agent = self.routes[selected]
            if hasattr(target_agent, "run") and hasattr(target_agent, "__call__"):
                # It's an Agent or agent-like object
                result_stream = await target_agent.run(prompt, context=context)
                async for ev in result_stream:
                    yield ev
            else:
                yield StreamEvent(type=EventType.error, content=f"Route '{selected}' is not a valid agent")

            yield StreamEvent(type=EventType.state, content="done",
                              data={"state": "done", "route": selected})
            yield StreamEvent(type=EventType.done)

        return Stream(_generate())
