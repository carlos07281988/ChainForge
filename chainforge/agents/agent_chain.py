"""AgentChain — 顺序组合多个 Agent，前一个输出传递到后一个。

Agent 版本的 Pipeline。每个步骤是一个 Agent，上一个 Agent 的输出
作为上下文传递给下一个 Agent。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from logging import INFO
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from chainforge.core.message import Message
from chainforge.core.stream import EventType, Stream, StreamEvent
from chainforge.core.tool import Tool, ToolSpec
from chainforge.logging import get_logger, log_data

logger = get_logger("agents.agent_chain")


class ChainStep(BaseModel):
    """A single step in an AgentChain."""

    name: str = Field(description="Step name")
    agent: Any = Field(description="The agent to run")
    description: str = Field(default="", description="What this step does")


class AgentChain(BaseModel):
    """Compose agents in sequence — each agent receives previous output as context.

    Can also be wrapped as a Tool for nesting inside other agents.

    Usage:
        chain = AgentChain(name="research_pipeline")
        chain.add_step("researcher", research_agent, "Researches the topic")
        chain.add_step("analyzer", analyze_agent, "Analyzes findings")
        chain.add_step("writer", write_agent, "Writes final report")

        stream = await chain.run("AI market trends 2026")
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = Field(default="agent_chain")
    steps: list[ChainStep] = Field(default_factory=list, description="Agents in sequence")
    max_iterations_per_step: int = Field(default=8)

    def add_step(self, name: str, agent: Any, description: str = "") -> "AgentChain":
        """Add an agent step to the chain."""
        self.steps.append(ChainStep(name=name, agent=agent, description=description))
        return self

    async def run(self, prompt: str | list, *, context: dict[str, Any] | None = None) -> Stream:
        """Execute the chain: each step passes its output to the next."""

        async def _generate() -> AsyncIterator[StreamEvent]:
            log_data(logger, INFO, f"AgentChain '{self.name}' started", data={"steps": len(self.steps)})

            yield StreamEvent(type=EventType.state, content="chain_start",
                              data={"state": "chain_start", "chain": self.name, "steps": len(self.steps)})

            current_prompt = prompt

            for i, step in enumerate(self.steps):
                step_num = i + 1
                yield StreamEvent(type=EventType.state, content="step_start",
                                  data={"state": "step_start", "step": step.name, "index": step_num, "total": len(self.steps)})
                yield StreamEvent(type=EventType.status,
                                  content=f"Step {step_num}/{len(self.steps)}: {step.name}")

                log_data(logger, INFO, f"Running step {step_num}: {step.name}",
                         data={"step": step.name, "index": step_num})

                # Run the agent for this step
                if hasattr(step.agent, "run") and hasattr(step.agent, "__call__"):
                    stream = await step.agent.run(current_prompt, context=context)
                    parts = []
                    async for event in stream:
                        if event.type == EventType.text and event.content:
                            parts.append(event.content)
                        if event.type != EventType.done:
                            yield event
                    step_output = "".join(parts)
                else:
                    step_output = f"[Step {step.name}: not a valid agent]"
                    yield StreamEvent(type=EventType.error, content=step_output)

                # Pass output to next step
                if isinstance(current_prompt, str):
                    ctx = current_prompt[:200] if len(current_prompt) > 200 else current_prompt
                    current_prompt = f"Context from previous step ({step.name}):\n{step_output}\n\nContinue the overall task. Original context: {ctx}"
                else:
                    current_prompt = list(current_prompt) + [
                        Message.assistant(step_output)
                    ]

                yield StreamEvent(type=EventType.state, content="step_done",
                                  data={"state": "step_done", "step": step.name, "output_length": len(step_output)})

            yield StreamEvent(type=EventType.state, content="chain_done",
                              data={"state": "chain_done", "chain": self.name})
            yield StreamEvent(type=EventType.done)

            log_data(logger, INFO, f"AgentChain '{self.name}' completed", data={"steps": len(self.steps)})

        return Stream(_generate())

    def to_tool(self, name: str | None = None, description: str | None = None) -> "ChainTool":
        """Wrap this chain as a Tool for nesting inside other agents."""
        return ChainTool(
            chain=self,
            name=name or self.name,
            description=description or f"Chain of {len(self.steps)} agents",
        )


class ChainTool:
    """Wrap an AgentChain as a Tool."""

    def __init__(self, chain: AgentChain, name: str, description: str):
        self._chain = chain
        self._name = name
        self._description = description
        self._spec = ToolSpec(
            name=self._name,
            description=self._description,
            parameters={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "The task for this agent chain",
                    }
                },
                "required": ["task"],
            },
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    async def run(self, task: str = "", **kwargs: Any) -> str:
        prompt = task if task else str(kwargs)
        stream = await self._chain.run(prompt)
        parts = []
        async for event in stream:
            if event.type == "text" and event.content:
                parts.append(event.content)
        return "".join(parts)

    def __call__(self, task: str = "", **kwargs: Any) -> str:
        from chainforge.core.utils import run_sync
        return run_sync(self.run(task=task, **kwargs))
