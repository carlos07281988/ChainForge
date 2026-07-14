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
"""Agent Inspector — debug and monitor agent execution in real-time.

Provides:
  - Inspector singleton: collects agent execution events
  - API endpoints: query agent state, events, summaries
  - Dashboard page: browser-based inspector UI

Usage:
    from chainforge.inspector import inspector

    # Record events during agent execution
    inspector.start_run("agent-1")
    inspector.record_event("agent-1", "state", state="thinking", iteration=1)
    inspector.end_run("agent-1")

    # Query
    events = inspector.get_events("agent-1")
    summary = inspector.get_summary("agent-1")
"""

from chainforge.inspector.inspector import (
    AgentInspector,
    AgentInspection,
    InspectionEvent,
    inspector,
)

__all__ = [
    "AgentInspector",
    "AgentInspection",
    "InspectionEvent",
    "inspector",
]
