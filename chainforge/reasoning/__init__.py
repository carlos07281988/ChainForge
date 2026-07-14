"""Reasoning Strategies — composable thinking patterns for agents.

Provides framework-level hooks that inject into the Agent loop:

  - ChainOfThought: step-by-step reasoning
  - ReasoningSteps: explicit sub-step planning
  - SelfReflection: self-critique and improvement
  - Verification: double-check before final answer
  - ReasoningStrategy: base class for custom strategies

Usage:
    from chainforge.reasoning import ChainOfThought, SelfReflection

    agent = Agent(
        llm=llm,
        reasoning=[ChainOfThought(), SelfReflection()],
    )
"""

from chainforge.reasoning.base import ReasoningStrategy
from chainforge.reasoning.cot import ChainOfThought, ReasoningSteps
from chainforge.reasoning.reflection import SelfReflection, Verification

__all__ = [
    "ReasoningStrategy",
    "ChainOfThought",
    "ReasoningSteps",
    "SelfReflection",
    "Verification",
]
