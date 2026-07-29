# Copyright 2026 ChainForge Contributors. Apache 2.0.
"""Handoff Protocol — async middleware that creates handoff packages on agent failure."""

from __future__ import annotations

from typing import Callable

from chainforge.enterprise.handoff.package import HandoffPackage, HandoffSLA
from chainforge.enterprise.handoff.queue import HandoffQueue


class HandoffProtocol:
    """Captures agent errors/retries and auto-creates handoff packages.

    The middleware wraps each agent invocation so that when the agent
    cannot resolve on its own (errors or max iterations reached), a
    ``HandoffPackage`` is automatically created and enqueued.
    """

    def __init__(self, queue: HandoffQueue | None = None) -> None:
        self._queue = queue or HandoffQueue()

    @property
    def queue(self) -> HandoffQueue:
        """The underlying handoff queue."""
        return self._queue

    def middleware(self) -> Callable:
        """Return an ASGI-style async middleware callable.

        The returned function has the signature::

            async def mw(request, call_next) -> Response

        When the downstream call raises an unhandled exception the
        middleware traps it, builds a ``HandoffPackage``, enqueues it,
        and re-raises so the caller can still decide how to respond.
        """

        async def _mw(request, call_next):
            # Stash request on an attribute so create_package can inspect it.
            self._last_request = request
            try:
                response = await call_next(request)
                return response
            except Exception as exc:
                pkg = self.create_package(
                    failed_reason=str(exc),
                    attempted_actions=getattr(
                        request.state, "attempted_actions", []
                    ),
                    relevant_context=getattr(
                        request.state, "handoff_context", {}
                    ),
                )
                self._queue.enqueue(pkg)
                raise

        return _mw

    def create_package(self, **kwargs) -> HandoffPackage:
        """Build a ``HandoffPackage`` merging call-site kwargs with defaults."""
        defaults: dict = {
            "run_id": kwargs.pop(
                "run_id", getattr(self, "_last_run_id", "unknown")
            ),
            "summary": kwargs.pop("summary", "Agent handoff required"),
            "attempted_actions": kwargs.pop("attempted_actions", []),
            "failed_reason": kwargs.pop("failed_reason", "Unknown"),
            "relevant_context": kwargs.pop("relevant_context", {}),
            "suggested_next_steps": kwargs.pop("suggested_next_steps", []),
            "priority": kwargs.pop("priority", "medium"),
            "agent_name": kwargs.pop("agent_name", ""),
            "sla": kwargs.pop("sla", None),
        }
        defaults.update(kwargs)
        return HandoffPackage(**defaults)

    def should_handoff(
        self, errors: bool, max_iterations: int, current_iteration: int
    ) -> bool:
        """Determine whether the agent should hand off to a human.

        Returns ``True`` when the agent has encountered errors and the
        maximum number of retry iterations has been exhausted.
        """
        if errors and current_iteration >= max_iterations:
            return True
        return False
