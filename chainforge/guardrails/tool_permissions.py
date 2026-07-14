"""Tool permission guardrails — restrict which tools an agent can call."""

from __future__ import annotations

from typing import Any

from chainforge.guardrails.base import (
    GuardrailAction,
    GuardrailResult,
    GuardrailSeverity,
    block_result,
    pass_result,
)
from chainforge.logging import get_logger

logger = get_logger("guardrails.tool_permissions")


class ToolPermissionPolicy:
    """Defines which tools are allowed or blocked for an agent.

    Args:
        allowed_tools: Set of tool names that are allowed. Empty = allow all.
        blocked_tools: Set of tool names that are explicitly blocked.
        require_approval: Set of tool names that require human-in-the-loop approval.
        dangerous_tools: Set of tool names that are considered dangerous (blocked by default).
    """

    def __init__(
        self,
        allowed_tools: set[str] | None = None,
        blocked_tools: set[str] | None = None,
        require_approval: set[str] | None = None,
        dangerous_tools: set[str] | None = None,
    ):
        self.allowed_tools = allowed_tools or set()
        self.blocked_tools = blocked_tools or set()
        self.require_approval = require_approval or set()
        self.dangerous_tools = dangerous_tools or {
            "execute_bash",
            "execute_python",
            "exec",
            "system",
            "shell",
            "rm",
            "sudo",
        }

    async def check_tool_call(
        self,
        tool_name: str,
        args: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> GuardrailResult:
        """Check if a tool call is allowed.

        Args:
            tool_name: Name of the tool being called.
            args: Arguments to the tool (optional).
            context: Additional context (user_id, session, etc.).

        Returns:
            GuardrailResult indicating pass/fail.
        """
        # Check dangerous tools
        if tool_name in self.dangerous_tools and tool_name not in self.allowed_tools:
            logger.warning(f"Dangerous tool blocked: {tool_name}")
            return block_result(
                reason=f"Tool '{tool_name}' is blocked by security policy",
                category="tool_permission",
                severity=GuardrailSeverity.high,
                metadata={"tool": tool_name, "reason": "dangerous_tool"},
            )

        # Check explicitly blocked
        if tool_name in self.blocked_tools:
            logger.warning(f"Blocked tool called: {tool_name}")
            return block_result(
                reason=f"Tool '{tool_name}' is blocked",
                category="tool_permission",
                severity=GuardrailSeverity.medium,
                metadata={"tool": tool_name, "reason": "blocked"},
            )

        # Check allowed list
        if self.allowed_tools and tool_name not in self.allowed_tools:
            logger.warning(f"Tool not in allowed list: {tool_name}")
            return block_result(
                reason=f"Tool '{tool_name}' is not in the allowed list",
                category="tool_permission",
                severity=GuardrailSeverity.medium,
                metadata={"tool": tool_name, "allowed": list(self.allowed_tools)},
            )

        # Check approval requirement
        if tool_name in self.require_approval:
            return GuardrailResult(
                passed=True,
                action=GuardrailAction.flag,  # Will trigger HITL
                severity=GuardrailSeverity.low,
                reason=f"Tool '{tool_name}' requires approval",
                category="tool_permission",
                risk_score=0.3,
                metadata={"tool": tool_name, "requires_approval": True},
            )

        return pass_result(category="tool_permission")
