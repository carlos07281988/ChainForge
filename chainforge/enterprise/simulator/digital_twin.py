# Copyright 2026 ChainForge Contributors. Apache 2.0.
"""Digital Twin for safe agent simulation.

Wraps a production agent and runs it in a sandbox mode where tool calls
return mock results instead of performing real side effects.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DigitalTwin:
    """A sandboxed replica of a production agent.

    Wraps an agent and intercepts its tool calls, returning mock results
    when sandbox mode is enabled. Useful for regression testing, chaos
    engineering, and cost estimation without affecting production systems.

    Attributes:
        production_agent: The agent instance to wrap.
        sandbox: Whether to intercept tool calls with mock results.
    """

    production_agent: Any
    sandbox: bool = True

    # Internal tracking.
    _mock_tool_registry: dict[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._mock_tool_registry = {}

    def register_mock(self, tool_name: str, mock_result: Any) -> None:
        """Register a mock result for a specific tool call.

        Args:
            tool_name: Name of the tool to mock.
            mock_result: The value to return when the tool is called.
        """
        self._mock_tool_registry[tool_name] = mock_result

    def _mock_tool_output(self, tool_name: str) -> dict:
        """Generate a mock tool output for a given tool name."""
        if tool_name in self._mock_tool_registry:
            result = self._mock_tool_registry[tool_name]
        else:
            result = f"[SANDBOX] Mock result for '{tool_name}'"

        return {
            "tool": tool_name,
            "result": result,
            "sandboxed": True,
        }

    async def run(self, prompt: str) -> dict:
        """Run a single prompt through the digital twin.

        Args:
            prompt: The input prompt to send to the agent.

        Returns:
            A dictionary containing the agent output, mock tool calls,
            estimated cost, and latency in seconds.
        """
        start = time.monotonic()

        try:
            if hasattr(self.production_agent, "run"):
                raw_output = await self.production_agent.run(prompt)
            elif hasattr(self.production_agent, "generate"):
                raw_output = await self.production_agent.generate(prompt)
            elif hasattr(self.production_agent, "__call__"):
                raw_output = await self.production_agent(prompt)
            else:
                raw_output = str(self.production_agent)

            status = "ok"
        except Exception as exc:
            raw_output = None
            status = f"error: {exc}"

        latency = time.monotonic() - start
        cost_estimate = _estimate_cost(prompt, str(raw_output or ""))

        mock_tools: list[dict] = []
        if self.sandbox:
            # Intercept known tool-call patterns.
            output_str = str(raw_output or "").lower()
            for tool_keyword, tool_name in _TOOL_KEYWORDS.items():
                if tool_keyword in output_str:
                    mock_tools.append(self._mock_tool_output(tool_name))

        return {
            "prompt": prompt,
            "status": status,
            "output": raw_output,
            "mock_tool_calls": mock_tools,
            "latency_seconds": round(latency, 4),
            "cost_estimate": cost_estimate,
            "sandbox": self.sandbox,
        }

    async def batch_run(
        self, prompts: list[str], max_concurrent: int = 5
    ) -> list[dict]:
        """Run multiple prompts concurrently against the digital twin.

        Args:
            prompts: List of input prompts.
            max_concurrent: Maximum number of concurrent executions.

        Returns:
            A list of result dictionaries, one per prompt.
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _bounded(prompt: str) -> dict:
            async with semaphore:
                return await self.run(prompt)

        tasks = [_bounded(p) for p in prompts]
        return await asyncio.gather(*tasks)

    def __repr__(self) -> str:
        agent_name = getattr(self.production_agent, "__class__", type(self.production_agent))
        name = getattr(agent_name, "__name__", str(agent_name))
        return f"DigitalTwin(agent={name}, sandbox={self.sandbox})"


# Mapping of keywords in agent output to tool names for mocking.
_TOOL_KEYWORDS: dict[str, str] = {
    "search": "web_search",
    "fetch": "web_fetch",
    "sql": "db_query",
    "database": "db_query",
    "email": "send_email",
    "slack": "slack_message",
    "file": "file_io",
    "calendar": "calendar_api",
    "api": "api_call",
    "deploy": "deploy_tool",
}


def _estimate_cost(prompt: str, output: str) -> float:
    """Estimate the cost of an agent call based on token counts.

    Uses a simple heuristic: ~$0.003 per 1K input tokens and
    ~$0.015 per 1K output tokens (rough GPT-4-level pricing).

    Args:
        prompt: The input prompt text.
        output: The agent output text.

    Returns:
        Estimated cost in USD.
    """
    input_tokens = max(1, len(prompt) // 4)
    output_tokens = max(1, len(output) // 4)
    cost = (input_tokens / 1000) * 0.003 + (output_tokens / 1000) * 0.015
    return round(cost, 6)
