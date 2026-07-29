# Copyright 2026 ChainForge Contributors. Apache 2.0.
"""RBAC middleware — intercept tool calls and enforce RBAC policies."""

from __future__ import annotations

from typing import Any, Callable


def rbac_middleware(rbac: "AgentRBAC") -> Callable:  # noqa: F821
    """Create an async middleware that intercepts tool_call events.

    The middleware wraps a handler function and evaluates RBAC policies
    before allowing the tool call to proceed. If access is denied, a
    PermissionError is raised (or the error is returned depending on
    the calling convention).

    Args:
        rbac: An AgentRBAC instance with loaded policies.

    Returns:
        An async middleware function suitable for use with agent frameworks.

    Example:
        rbac = AgentRBAC(policies=[RBACPolicy.create_default()])
        middleware = rbac_middleware(rbac)

        @middleware
        async def tool_handler(tool_call, agent_context):
            ...
    """

    async def middleware_wrapper(
        handler: Callable,
        tool_call: dict[str, Any],
        agent_context: dict[str, Any] | None = None,
    ) -> Any:
        """Intercept a tool call and enforce RBAC policies.

        Args:
            handler: The next handler in the chain (async callable).
            tool_call: The tool call dict with at least 'name' and 'args'.
            agent_context: Agent identity and request context dict with keys:
                - agent_identity (dict): verified, clearance, roles, etc.
                - data_labels (list[str]): data classification labels.
                - context (dict): additional request context.

        Returns:
            The result from the handler, or raises PermissionError.
        """
        agent_context = agent_context or {}

        # Extract RBAC-relevant fields
        action = tool_call.get("name", tool_call.get("action", "unknown"))
        agent_identity = agent_context.get("agent_identity", {})
        data_labels = agent_context.get("data_labels", [])
        extra_context = agent_context.get("context", {})

        # Evaluate access
        decision = rbac.evaluate(
            action=action,
            agent_identity=agent_identity,
            data_labels=data_labels,
            context=extra_context,
        )

        if not decision.allowed:
            raise PermissionError(
                f"RBAC denied tool '{action}': {decision.reason} "
                f"(audit_id: {decision.audit_id})"
            )

        # Access granted — pass through to handler
        if callable(handler):
            result = handler(tool_call) if agent_context is None else handler(tool_call, agent_context)

            # Handle both sync and async handlers
            if hasattr(result, "__await__"):
                return await result
            return result

        return None

    return middleware_wrapper
