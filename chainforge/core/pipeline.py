"""Pipeline — compose processing steps into a linear or branched workflow.

A simpler, more predictable alternative to LCEL. Each step is a function
that receives the previous output and returns a new value.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

from pydantic import BaseModel, Field

from chainforge.core.stream import EventType, Stream, StreamEvent

# Type aliases (avoiding `type` keyword for Python 3.11 compat)
StepFn = Callable[[Any], Any]
AsyncStepFn = Callable[[Any], Any]


class Pipeline(BaseModel):
    """A sequence of processing steps that passes data through each one.

    Usage:
        pipe = Pipeline(
            "Extract -> Translate -> Summarize",
            steps=[extract, translate, summarize],
        )
        result = await pipe.run(input_text)
    """

    name: str = Field(default="pipeline", description="Pipeline name")
    steps: list = Field(default_factory=list, description="List of step functions")

    async def run(self, input: Any) -> Any:
        """Run pipeline synchronously (async), passing data through each step."""
        current = input
        for step in self.steps:
            result = step(current)
            if hasattr(result, "__await__"):
                current = await result
            else:
                current = result
        return current

    def stream(self, input: Any) -> Stream:
        """Run pipeline with streaming events per step."""

        async def _generate() -> AsyncIterator[StreamEvent]:
            current = input
            for i, step in enumerate(self.steps):
                step_name = getattr(step, "__name__", f"step_{i}")
                yield StreamEvent(type=EventType.status, content=f"Running step: {step_name}")
                try:
                    result = step(current)
                    if hasattr(result, "__await__"):
                        current = await result
                    else:
                        current = result
                    yield StreamEvent(type=EventType.text, content=str(current))
                except Exception as e:
                    yield StreamEvent(type=EventType.error, content=str(e))
                    raise
            yield StreamEvent(type=EventType.done)

        return Stream(_generate())

    def __rshift__(self, other: StepFn | "Pipeline") -> "Pipeline":
        """Allow composing pipelines with >> operator."""
        if isinstance(other, Pipeline):
            return Pipeline(name=f"{self.name} >> {other.name}", steps=self.steps + other.steps)
        return Pipeline(name=f"{self.name} >> {getattr(other, '__name__', '?')}", steps=self.steps + [other])

    def __call__(self, input: Any) -> Any:
        """Convenience: call the pipeline directly."""
        import asyncio
        return asyncio.run(self.run(input))
