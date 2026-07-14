# Copyright 2024 ChainForge Contributors
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
