"""Callbacks — structured observability hooks for Agent execution.

The third pillar of ChainForge's agent lifecycle system:
- Middleware: modifies the stream
- ReasoningStrategy: modifies behavior
- Callback: observes and records (one-way)

Usage:
    from chainforge.callbacks import LoggingCallback, MetricsCallback

    agent = Agent(
        llm=llm,
        callbacks=[LoggingCallback(), MetricsCallback()],
    )
"""

from chainforge.callbacks.base import Callback, BaseCallback
from chainforge.callbacks.logging import LoggingCallback
from chainforge.callbacks.metrics import MetricsCallback

__all__ = [
    "Callback",
    "BaseCallback",
    "LoggingCallback",
    "MetricsCallback",
]
