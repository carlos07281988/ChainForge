"""AgentTool — 将任意 Agent 包装为 Tool，供其他 Agent 调用。

实现层次化 Agent 系统：一个 Agent 可以调用另一个 Agent 来完成子任务。
"""

from __future__ import annotations

from logging import INFO
from typing import Any

from chainforge.core.tool import Tool, ToolSpec
from chainforge.logging import get_logger, log_data

logger = get_logger("agents.agent_tool")


class AgentTool:
    """Wrap an Agent as a Tool that other agents can call.

    The wrapped agent runs as a sub-task when called, and its text output
    is returned as the tool result.

    Usage:
        search_agent = Agent(llm=llm, tools=[search])
        search_tool = AgentTool(search_agent, name="search_specialist",
                                description="Search for information")

        main_agent = Agent(llm=llm, tools=[search_tool, weather_tool])
        async for event in await main_agent.run("Find info on AI"):
            ...
    """

    def __init__(
        self,
        agent: Any,
        name: str | None = None,
        description: str | None = None,
        timeout_seconds: float | None = None,
    ):
        self._agent = agent
        self._name = name or getattr(agent, "__class__", type(agent)).__name__
        self._description = description or getattr(agent, "system_prompt", "An agent tool") or "Agent tool"
        self._timeout = timeout_seconds
        self._spec = ToolSpec(
            name=self._name,
            description=self._description,
            parameters={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "The task or question for this agent",
                    }
                },
                "required": ["task"],
            },
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    async def run(self, task: str = "", **kwargs: Any) -> str:
        """Run the wrapped agent with the given task and return text output."""
        log_data(logger, INFO, f"AgentTool '{self._name}' called", data={"task_length": len(task)})

        prompt = task if task else str(kwargs) if kwargs else "Execute your function."

        stream = await self._agent.run(prompt)
        parts: list[str] = []
        async for event in stream:
            if event.type == "text" and event.content:
                parts.append(event.content)

        result = "".join(parts)
        log_data(logger, INFO, f"AgentTool '{self._name}' done", data={"output_length": len(result)})
        return result or f"[{self._name}: completed with no text output]"

    def __call__(self, task: str = "", **kwargs: Any) -> str:
        import asyncio
        return asyncio.run(self.run(task=task, **kwargs))

    def __repr__(self) -> str:
        return f"AgentTool(name={self._name!r})"
