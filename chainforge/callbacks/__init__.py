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
