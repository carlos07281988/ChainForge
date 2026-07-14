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
"""Guardrails — safety and security for agent inputs, outputs, and tool calls.

Provides:
  - Input guards: injection detection, topic filter, PII filter
  - Output guards: PII leak prevention, content safety, quality checks
  - Tool permission policies: allow/block lists, dangerous tool protection
  - Middleware integration: plug into any ChainForge Agent

Usage:
    from chainforge.guardrails.input import InjectionDetector, TopicFilter
    from chainforge.guardrails.output import PIILeakGuard, ContentSafetyGuard
    from chainforge.guardrails.middleware import GuardrailMiddleware

    agent = Agent(
        llm=llm,
        middlewares=[
            GuardrailMiddleware(guardrails=[
                ("input", InjectionDetector()),
                ("output", PIILeakGuard()),
            ]),
        ],
    )
"""

from chainforge.guardrails.base import (
    GuardrailAction,
    GuardrailResult,
    GuardrailSeverity,
    pass_result,
    block_result,
    flag_result,
)
from chainforge.guardrails.input import InjectionDetector, TopicFilter, SensitiveDataFilter
from chainforge.guardrails.output import PIILeakGuard, ContentSafetyGuard, QualityGuard
from chainforge.guardrails.tool_permissions import ToolPermissionPolicy
from chainforge.guardrails.middleware import GuardrailMiddleware, GuardrailBlocked

__all__ = [
    "GuardrailAction",
    "GuardrailResult",
    "GuardrailSeverity",
    "guardrail",
    "pass_result",
    "block_result",
    "flag_result",
    "InjectionDetector",
    "TopicFilter",
    "SensitiveDataFilter",
    "PIILeakGuard",
    "ContentSafetyGuard",
    "QualityGuard",
    "ToolPermissionPolicy",
    "GuardrailMiddleware",
    "GuardrailBlocked",
]
