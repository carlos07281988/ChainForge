# Copyright 2026 ChainForge Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Supervisor — hierarchical delegation with recursive worker nesting.

The Supervisor receives a task, plans how to break it down,
delegates sub-tasks to worker agents (which may themselves be Supervisors),
and synthesizes the final result.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

import re

from chainforge.core.agent import Agent
from chainforge.core.message import Message
from chainforge.core.stream import EventType, Stream, StreamEvent
from chainforge.logging import get_logger

logger = get_logger("orchestration.supervisor")


class Supervisor(BaseModel):
    """A supervising agent that delegates to specialized workers.

    Supports hierarchical teams: workers can themselves be Supervisor
    instances, enabling recursive delegation (e.g. CTO -> Manager -> Engineer).

    Usage:
        # Flat delegation
        supervisor = Supervisor(
            supervisor_agent=planner_agent,
            workers={
                "search": search_agent,
                "analyze": analyze_agent,
            },
        )

        # Hierarchical: worker is itself a Supervisor
        engineer_team = Supervisor(supervisor_agent=tech_lead, workers={...})
        supervisor = Supervisor(
            supervisor_agent=cto_agent,
            workers={"engineering": engineer_team},
        )
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    supervisor_agent: Agent = Field(description="Agent that plans and delegates")
    workers: dict[str, Any] = Field(default_factory=dict, description="Worker agents (may be Supervisor)")
    max_delegations: int = Field(default=5, description="Max delegation rounds")

    async def run(self, prompt: str | list[Message], *, context: dict[str, Any] | None = None) -> Stream:
        """Execute the supervisor pattern with hierarchical delegation."""

        async def _generate() -> AsyncIterator[StreamEvent]:
            if isinstance(prompt, str):
                messages = [Message.system(self._build_system_prompt()), Message.user(prompt)]
            else:
                messages = [Message.system(self._build_system_prompt())] + list(prompt)

            yield StreamEvent(type=EventType.status, content="Supervisor started")

            for round_num in range(self.max_delegations):
                yield StreamEvent(type=EventType.status, content=f"Delegation round {round_num + 1}")

                # Supervisor decides what to do
                stream = await self.supervisor_agent.run(messages, context=context)
                supervisor_response = ""
                async for event in stream:
                    if event.type == EventType.text and event.content:
                        supervisor_response += event.content
                    yield event

                # Check if supervisor wants to delegate
                delegated = False
                for worker_name, worker_agent in self.workers.items():
                    if re.search(r'\b' + re.escape(worker_name.lower()) + r'\b', supervisor_response.lower()):
                        delegated = True
                        yield StreamEvent(
                            type=EventType.status,
                            content=f"Delegating to worker: {worker_name}",
                        )

                        worker_task = f"Task: {supervisor_response[:500]}"

                        # Recursive delegation if worker is also a Supervisor
                        if isinstance(worker_agent, Supervisor):
                            worker_stream = await worker_agent.run(
                                [Message.user(f"Supervisor task: {supervisor_response[:500]}")],
                                context=context,
                            )
                        elif hasattr(worker_agent, "run"):
                            worker_stream = await worker_agent.run(
                                [Message.user(worker_task)],
                                context=context,
                            )
                        else:
                            yield StreamEvent(type=EventType.error,
                                              content=f"Worker '{worker_name}' is not a valid agent")
                            continue

                        worker_output = ""
                        async for event in worker_stream:
                            if event.type == EventType.text and event.content:
                                worker_output += event.content
                            if event.type != EventType.done:
                                yield event

                        # Report worker result back to supervisor
                        messages.append(Message.assistant(supervisor_response))
                        messages.append(Message.user(
                            f"[Worker {worker_name} result]:\n{worker_output}"
                        ))
                        break

                if not delegated:
                    # Supervisor answered directly (no delegation needed)
                    break

            yield StreamEvent(type=EventType.done)

        return Stream(_generate())

    def _build_system_prompt(self) -> str:
        worker_list = "\n".join(f"  - {name}" for name in self.workers)

        # Detect hierarchical depth
        has_sub_supervisors = any(
            isinstance(w, Supervisor) for w in self.workers.values()
        )
        hierarchy_note = (
            "\nNote: Some workers are themselves team supervisors. "
            "You can delegate to a team and they will handle sub-delegation."
            if has_sub_supervisors else ""
        )

        return f"""You are a supervisor agent that delegates tasks to specialized workers.

Available workers:
{worker_list}
{hierarchy_note}

Your job:
1. Analyze the user's request
2. Decide which worker(s) to involve, or answer directly
3. If delegating, tell the user which worker you're using
4. Synthesize worker results into a final answer

When you mention a worker name (e.g., "{list(self.workers.keys())[0] if self.workers else 'worker'}"),
the system will automatically delegate to that worker.
"""

    def add_worker(self, name: str, agent: Any) -> "Supervisor":
        """Add a worker agent (or sub-Supervisor) to the team."""
        self.workers[name] = agent
        return self
