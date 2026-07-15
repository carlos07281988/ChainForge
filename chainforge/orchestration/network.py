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
"""Network topology — agents communicate freely via message bus.

In a Network topology, agents can:
- Broadcast messages to all other agents
- Send direct messages to specific agents
- Subscribe to topics
- Route messages based on content/type
- Work concurrently without a central supervisor

Usage:
    network = AgentNetwork(name="research_team")
    network.add_agent("researcher", researcher_agent)
    network.add_agent("analyzer", analyzer_agent, subscriptions=["analysis"])
    network.add_agent("writer", writer_agent, subscriptions=["result"])

    async for event in network.run("Research AI trends"):
        ...
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from chainforge.core.stream import EventType, Stream, StreamEvent
from chainforge.logging import get_logger

logger = get_logger("orchestration.network")


class MessageEnvelope(BaseModel):
    """A message in the agent network."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender: str = Field(description="Sender agent ID")
    recipient: str | None = Field(default=None, description="Direct recipient or None for broadcast")
    topic: str = Field(default="general", description="Message topic")
    content: str = Field(description="Message body")
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentNetwork(BaseModel):
    """A network of communicating agents with pub/sub messaging.

    Agents communicate through a message bus, not through a central supervisor.
    Each agent can subscribe to topics and send/receive messages.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = Field(default="agent_network")
    agents: dict[str, Any] = Field(default_factory=dict, description="Agent ID -> Agent instance")
    subscriptions: dict[str, list[str]] = Field(default_factory=dict, description="Agent ID -> list of topics")
    max_rounds: int = Field(default=3, description="Max communication rounds")

    async def run(self, prompt: str | list, *, context: dict[str, Any] | None = None) -> Stream:
        """Execute the network on the given prompt."""

        async def _generate() -> AsyncIterator[StreamEvent]:
            user_prompt = prompt if isinstance(prompt, str) else (prompt[-1].content if prompt[-1].content else "")
            yield StreamEvent(type=EventType.status, content=f"Network '{self.name}' started ({len(self.agents)} agents)")

            # Message bus
            bus: list[MessageEnvelope] = []

            # Initial message to all agents
            bus.append(MessageEnvelope(
                sender="__system__",
                recipient=None,
                topic="task",
                content=user_prompt,
            ))

            round_num = 0
            while round_num < self.max_rounds:
                yield StreamEvent(
                    type=EventType.state,
                    content=f"round:{round_num}",
                    data={"state": "communicating", "round": round_num + 1, "total": self.max_rounds},
                )

                # Messages for this round (first round includes task message)
                round_messages: list[MessageEnvelope] = []
                for m in bus:
                    md_round = m.metadata.get("round")
                    if md_round is None and round_num == 0:
                        round_messages.append(m)
                    elif md_round == round_num:
                        round_messages.append(m)

                if not round_messages and round_num > 0:
                    yield StreamEvent(type=EventType.status, content="No more messages, stopping")
                    break

                new_messages: list[MessageEnvelope] = []

                for agent_id, agent_obj in self.agents.items():
                    # Determine this agent's inbox
                    inbox: list[MessageEnvelope] = []
                    for msg in round_messages:
                        if msg.recipient is None or msg.recipient == agent_id:
                            inbox.append(msg)
                        elif agent_id in self.subscriptions.get(msg.sender, []):
                            inbox.append(msg)

                    if not inbox:
                        continue

                    for msg in inbox:
                        agent_prompt = (
                            f"[Network Round {round_num + 1}]\n"
                            f"From: {msg.sender}\n"
                            f"Topic: {msg.topic}\n"
                            f"Message: {msg.content}\n"
                            f"\nRespond with your contribution. "
                            f"To send a direct message, start a line with TO:<agent_id>: <message>. "
                            f"To broadcast, start a line with BROADCAST: <message>."
                        )

                        try:
                            if hasattr(agent_obj, "run"):
                                stream = await agent_obj.run(agent_prompt, context=context)
                                parts: list[str] = []
                                async for ev in stream:
                                    if ev.type == EventType.text and ev.content:
                                        parts.append(ev.content)
                                    if ev.type != EventType.done:
                                        yield ev
                                response = "".join(parts)
                            else:
                                response = f"[{agent_id}: no run method]"
                                yield StreamEvent(type=EventType.error, content=response)

                            # Parse for directed messages
                            lines = response.split("\n")
                            has_directed = False
                            for line in lines:
                                line_stripped = line.strip()
                                if line_stripped.startswith("TO:"):
                                    has_directed = True
                                    rest = line_stripped[3:].strip()
                                    colon_pos = rest.find(":")
                                    if colon_pos > 0:
                                        target = rest[:colon_pos].strip()
                                        content_after = rest[colon_pos + 1:].strip()
                                    else:
                                        target = rest.split()[0] if rest else ""
                                        content_after = " ".join(rest.split()[1:]) if len(rest.split()) > 1 else response
                                    if target and target in self.agents:
                                        new_messages.append(MessageEnvelope(
                                            sender=agent_id,
                                            recipient=target,
                                            topic="direct",
                                            content=content_after or response,
                                            metadata={"round": round_num + 1},
                                        ))
                                elif line_stripped.startswith("BROADCAST"):
                                    has_directed = True
                                    content_bc = line_stripped[len("BROADCAST"):].strip() or response
                                    new_messages.append(MessageEnvelope(
                                        sender=agent_id,
                                        recipient=None,
                                        topic="broadcast",
                                        content=content_bc,
                                        metadata={"round": round_num + 1},
                                    ))

                            # If no directed messages, send as general topic contribution
                            if not has_directed:
                                topics = self.subscriptions.get(agent_id, ["general"])
                                for topic in topics:
                                    new_messages.append(MessageEnvelope(
                                        sender=agent_id,
                                        recipient=None,
                                        topic=topic,
                                        content=response,
                                        metadata={"round": round_num + 1},
                                    ))

                        except Exception as e:
                            logger.error(f"Network agent {agent_id} failed: {e}")
                            new_messages.append(MessageEnvelope(
                                sender=agent_id,
                                recipient="__system__",
                                topic="error",
                                content=f"Error: {e}",
                                metadata={"round": round_num + 1},
                            ))

                bus.extend(new_messages)

                if not new_messages:
                    break

                round_num += 1

            yield StreamEvent(type=EventType.state, content="done", data={
                "state": "done", "rounds": round_num + 1, "total_messages": len(bus),
            })
            yield StreamEvent(type=EventType.done)

        return Stream(_generate())

    def add_agent(self, agent_id: str, agent: Any, subscriptions: list[str] | None = None) -> "AgentNetwork":
        """Add an agent to the network with optional topic subscriptions."""
        self.agents[agent_id] = agent
        if subscriptions:
            self.subscriptions[agent_id] = subscriptions
        return self

    def remove_agent(self, agent_id: str) -> None:
        self.agents.pop(agent_id, None)
        self.subscriptions.pop(agent_id, None)
