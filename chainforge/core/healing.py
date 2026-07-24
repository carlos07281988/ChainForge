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
"""Self-Healing Agents — automatic failure detection, diagnosis, and recovery.

Wraps any Agent with tool-level healing: retry on failure, fallback to
alternative tools, error classification, and success tracking.

Usage:
    from chainforge.core.healing import SelfHealingWrapper, HealingPolicy

    policy = HealingPolicy(
        max_retries=2,
        fallback_tools={"web_search": ["web_fetch"]},
    )
    agent = SelfHealingWrapper(my_agent, policy=policy)
    stream = await agent.run("Search for AI news")
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field

from chainforge.core.agent import Agent
from chainforge.core.stream import EventType, Stream, StreamEvent
from chainforge.core.tool import FunctionTool, Tool
from chainforge.logging import get_logger

logger = get_logger("core.healing")


# ── Healing Policy ────────────────────────────────────────────────────────


class HealingPolicy(BaseModel):
    """Configuration for self-healing behavior.

    Controls how the SelfHealingWrapper handles tool failures:
    retry attempts, fallback tools, and error escalation.
    """

    max_retries: int = Field(default=2, description="Max retries per tool call")
    retry_delay: float = Field(default=0.5, description="Seconds between retries")
    retry_backoff: float = Field(default=1.5, description="Multiplicative backoff per retry")
    fallback_tools: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Tool name → list of fallback tool names",
    )
    track_failures: bool = Field(default=True, description="Track per-tool success/failure")
    auto_escalate: bool = Field(default=True, description="Send final error to LLM if all fallbacks fail")


# ── SelfHealingWrapper ───────────────────────────────────────────────────────


class SelfHealingWrapper:
    """Wraps an Agent with automatic tool-level healing.

    Intercepts tool execution and applies healing strategies:
      - Retry with exponential backoff
      - Fallback to alternative tools
      - Error classification
      - Success/failure tracking

    Usage:
        agent = SelfHealingWrapper(
            Agent(llm=llm, tools=[web_search, web_fetch]),
            policy=HealingPolicy(max_retries=2, fallback_tools={
                "web_search": ["web_fetch"],
            }),
        )
        stream = await agent.run("Search for AI news")
    """

    def __init__(self, agent: Agent, policy: HealingPolicy | None = None):
        self._agent = agent
        self._policy = policy or HealingPolicy()
        self._success_counts: dict[str, int] = defaultdict(int)
        self._failure_counts: dict[str, int] = defaultdict(int)
        self._fallback_map: dict[str, list[Tool]] = {}
        self._healed_count: int = 0
        self._total_failures: int = 0

    @property
    def agent(self) -> Agent:
        return self._agent

    # ── Stats ────────────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Get healing statistics."""
        per_tool = {}
        all_tools = set(self._success_counts) | set(self._failure_counts)
        for t in all_tools:
            s = self._success_counts.get(t, 0)
            f = self._failure_counts.get(t, 0)
            total = s + f
            per_tool[t] = {
                "calls": total,
                "successes": s,
                "failures": f,
                "success_rate": round(s / total, 3) if total > 0 else 1.0,
            }
        return {
            "total_calls": sum(self._success_counts.values()) + sum(self._failure_counts.values()),
            "successes": sum(self._success_counts.values()),
            "failures": self._total_failures,
            "healed": self._healed_count,
            "heal_rate": round(
                self._healed_count / self._total_failures, 3
            ) if self._total_failures > 0 else 1.0,
            "per_tool": per_tool,
        }

    def reset_stats(self) -> None:
        self._success_counts.clear()
        self._failure_counts.clear()
        self._healed_count = 0
        self._total_failures = 0

    # ── Run ──────────────────────────────────────────────────────────────

    async def run(
        self,
        prompt: str | list | None = None,
        *,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Stream:
        """Run the agent with self-healing enabled.

        All healing logic (retry, fallback, tracking) happens transparently.

        Args:
            prompt: User prompt or messages.
            context: Optional context.
            **kwargs: Additional args passed to Agent.run().

        Returns:
            Stream of events (same as Agent.run()).
        """
        # Get the full tool map including fallback tools
        all_tools = self._agent._all_tools()
        self._build_fallback_map(all_tools)

        # Wrap each tool with healing logic
        wrapped_tools = [self._wrap_tool(t) for t in all_tools]

        # Create a copy of the agent with wrapped tools
        healing_agent = self._agent.model_copy(update={"tools": wrapped_tools})

        return await healing_agent.run(prompt, context=context, **kwargs)

    def _build_fallback_map(self, all_tools: list[Tool]) -> None:
        """Build a map of tool name → fallback Tool objects."""
        tool_by_name = {t.spec.name: t for t in all_tools}
        self._fallback_map = {}
        for tool_name, fallback_names in self._policy.fallback_tools.items():
            fallbacks = []
            for fb_name in fallback_names:
                fb_tool = tool_by_name.get(fb_name)
                if fb_tool:
                    fallbacks.append(fb_tool)
                else:
                    logger.warning(f"Fallback tool '{fb_name}' not found")
            if fallbacks:
                self._fallback_map[tool_name] = fallbacks

    def _wrap_tool(self, tool: Tool) -> FunctionTool:
        """Wrap a single tool with healing logic.

        The wrapped tool:
        1. Tries the original tool (with retries)
        2. On failure, tries fallback tools
        3. Tracks success/failure stats
        """
        policy = self._policy
        fallbacks = self._fallback_map.get(tool.spec.name, [])
        original_name = tool.spec.name

        async def healing_run(**kwargs: Any) -> str:
            last_error: Exception | None = None
            last_error_str: str = ""

            # Try original tool with retries
            for attempt in range(policy.max_retries + 1):
                try:
                    result = await tool.run(**kwargs)
                    if policy.track_failures:
                        self._success_counts[original_name] += 1
                    return result
                except Exception as e:
                    last_error = e
                    last_error_str = str(e)
                    if policy.track_failures:
                        self._failure_counts[original_name] += 1
                        self._total_failures += 1
                    if attempt < policy.max_retries:
                        delay = policy.retry_delay * (policy.retry_backoff ** attempt)
                        logger.info(
                            f"Tool '{original_name}' failed (attempt {attempt + 1}): "
                            f"{e}. Retrying in {delay:.1f}s"
                        )
                        await asyncio.sleep(delay)

            # Original tool failed after all retries. Try fallback tools.
            for fb_tool in fallbacks:
                try:
                    result = await fb_tool.run(**kwargs)
                    if policy.track_failures:
                        self._healed_count += 1
                        self._success_counts[fb_tool.spec.name] += 1
                    logger.info(
                        f"Healed: '{original_name}' → fallback '{fb_tool.spec.name}'"
                    )
                    return result
                except Exception as e:
                    if policy.track_failures:
                        self._failure_counts[fb_tool.spec.name] += 1
                    last_error = e
                    last_error_str = str(e)

            # All attempts and fallbacks failed. Escalate or raise.
            error_msg = f"Tool '{original_name}' failed after {policy.max_retries + 1} "
            error_msg += f"attempt(s) and {len(fallbacks)} fallback(s): {last_error_str}"

            if policy.auto_escalate:
                # Return error message as result — the LLM can decide what to do
                logger.warning(error_msg)
                return f"Error: {error_msg}"
            raise last_error or RuntimeError(error_msg)

        return FunctionTool(
            healing_run,
            name=tool.spec.name,
            description=tool.spec.description,
        )


# ── Error classification ──────────────────────────────────────────────────


class ErrorCategory:
    """Classification of tool execution errors."""
    TOOL_ERROR = "tool_error"       # Exception during execution
    CONTENT_ERROR = "content_error"  # Error message in returned content
    TIMEOUT = "timeout"              # Tool timed out
    LLM_REFUSAL = "llm_refusal"     # LLM refused



def classify_error(error: Exception | str) -> str:
    """Classify a tool error into a category.

    Args:
        error: The exception or error message string.

    Returns:
        One of ErrorCategory values.
    """
    if isinstance(error, Exception):
        msg = str(error).lower()
        if "timeout" in msg:
            return ErrorCategory.TIMEOUT
        return ErrorCategory.TOOL_ERROR

    error_str = str(error).lower()
    if "refuse" in error_str or "cannot" in error_str or "sorry" in error_str:
        return ErrorCategory.LLM_REFUSAL
    if error_str.startswith("error:"):
        return ErrorCategory.CONTENT_ERROR
    return ErrorCategory.TOOL_ERROR


__all__ = [
    "HealingPolicy",
    "SelfHealingWrapper",
    "ErrorCategory",
    "classify_error",
]
