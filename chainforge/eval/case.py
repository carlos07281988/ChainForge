"""Eval case models — define what to test and what to measure."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, Field


class ExpectedBehavior(str, Enum):
    """Categorizes what kind of response is expected from the agent."""
    contains = "contains"           # Output should contain a specific string/pattern
    matches = "matches"             # Output should match a regex
    json_valid = "json_valid"       # Output should be valid JSON
    tool_called = "tool_called"     # Agent should have called a specific tool
    no_errors = "no_errors"         # Agent should not have errors
    max_tokens = "max_tokens"       # Response should be under token limit
    custom = "custom"               # Custom evaluator function


class EvalMetric(str, Enum):
    """Standard metrics that can be collected during evaluation."""
    response_time = "response_time"         # Total time to respond (seconds)
    tool_call_count = "tool_call_count"     # Number of tool calls made
    token_count = "token_count"             # Total tokens used
    iterations = "iterations"               # Number of agent iterations
    cost = "cost"                           # Estimated cost (USD)
    response_length = "response_length"     # Length of final text response
    success = "success"                     # Whether agent completed without errors


class EvalCase(BaseModel):
    """A single test case for evaluating an agent."""

    name: str = Field(description="Test case name")
    prompt: str = Field(description="Input prompt for the agent")
    expected: list[ExpectedBehavior] = Field(default_factory=list, description="Expected behavior checks")
    expected_contains: list[str] = Field(default_factory=list, description="Strings that should appear in output")
    expected_tool: str | None = Field(default=None, description="Specific tool the agent should call")
    context: Dict[str, Any] | None = Field(default=None, description="Optional context data")
    tags: list[str] = Field(default_factory=list, description="Tags for filtering/categorization")
    weight: float = Field(default=1.0, description="Weight for scoring (e.g., higher = more important)")
    custom_check: str | None = Field(default=None, description="Python expression evaluated with 'output' and 'events' vars")

    def dict(self, *args, **kwargs) -> dict[str, Any]:
        return self.model_dump(*args, **kwargs)


# Built-in test case collections

def sample_cases() -> list[EvalCase]:
    """Return a set of sample test cases for quick-start evaluation."""
    return [
        EvalCase(
            name="simple_greeting",
            prompt="Say hello!",
            expected=[ExpectedBehavior.contains],
            expected_contains=["hello", "Hello"],
            tags=["basic"],
        ),
        EvalCase(
            name="tool_usage",
            prompt="What is the weather in Beijing?",
            expected=[ExpectedBehavior.tool_called],
            expected_tool="get_weather",
            tags=["tools"],
        ),
        EvalCase(
            name="no_errors",
            prompt="Tell me a short joke.",
            expected=[ExpectedBehavior.no_errors],
            tags=["basic"],
        ),
    ]
