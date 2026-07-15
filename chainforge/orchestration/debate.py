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
"""Debate — multiple agents argue to reach consensus.

Agents take turns presenting arguments, counter-arguments, and
refinements until consensus is reached or max rounds exhausted.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from chainforge.core.message import Message
from chainforge.core.stream import EventType, Stream, StreamEvent
from chainforge.logging import get_logger

logger = get_logger("orchestration.debate")

CONSENSUS_CHECK_PROMPT = """Review the following debate on: {topic}

Arguments presented:
{transcript}

Has the group reached consensus? If so, what is the consensus position?
If not, what are the remaining disagreements?

Respond with exactly one line: CONSENSUS: <yes/no>
Then on the next line: POSITION: <the consensus or main disagreement>"""


class DebateAgent(BaseModel):
    """An agent participating in a debate."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = Field(description="Agent name")
    agent: Any = Field(description="Agent instance")
    stance: str = Field(default="", description="Initial stance or perspective")
    turn_order: int = Field(default=0, description="Speaking order")


class Debate(BaseModel):
    """Multi-agent debate to reach consensus on a topic.

    Usage:
        debate = Debate(name="policy_review", topic="Best AI safety approach")
        debate.add_debater("optimist", optimistic_agent, "AI will solve safety")
        debate.add_debater("skeptic", skeptic_agent, "AI poses existential risk")
        debate.add_debater("moderator", moderator_agent, "Let's find middle ground")

        async for event in debate.run():
            ...
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = Field(default="debate")
    topic: str = Field(description="Debate topic")
    debaters: list[DebateAgent] = Field(default_factory=list)
    max_rounds: int = Field(default=3, description="Max argument rounds")
    consensus_llm: Any | None = Field(default=None, description="LLM for consensus check")

    async def run(self, prompt: str | None = None, *, context: dict[str, Any] | None = None) -> Stream:
        async def _generate() -> AsyncIterator[StreamEvent]:
            topic = prompt or self.topic
            yield StreamEvent(type=EventType.status, content=f"Debate '{self.name}' started on: {topic}")

            if not self.debaters:
                yield StreamEvent(type=EventType.error, content="No debaters registered")
                yield StreamEvent(type=EventType.done)
                return

            # Sort by turn order
            sorted_debaters = sorted(self.debaters, key=lambda d: d.turn_order)
            transcript: list[str] = []

            yield StreamEvent(type=EventType.state, content=f"topic:{topic}",
                              data={"state": "topic_set", "topic": topic, "debaters": len(self.debaters)})

            for round_num in range(self.max_rounds):
                yield StreamEvent(type=EventType.state, content=f"round:{round_num + 1}",
                                  data={"state": "debating", "round": round_num + 1, "total": self.max_rounds})

                for debater in sorted_debaters:
                    context_str = "\n".join(transcript[-10:]) if transcript else "No prior arguments."

                    turn_prompt = (
                        f"Debate topic: {topic}\n"
                        f"Your stance: {debater.stance}\n"
                        f"You are: {debater.name}\n\n"
                        f"Current transcript:\n{context_str}\n\n"
                        f"Round {round_num + 1}/{self.max_rounds}. "
                        f"Present your argument, respond to others, or refine your position."
                    )

                    yield StreamEvent(type=EventType.status, content=f"{debater.name} speaking (round {round_num + 1})...")

                    try:
                        if hasattr(debater.agent, "run"):
                            stream = await debater.agent.run(turn_prompt, context=context)
                            parts = []
                            async for ev in stream:
                                if ev.type == EventType.text and ev.content:
                                    parts.append(ev.content)
                                if ev.type != EventType.done:
                                    yield ev
                            response = "".join(parts)
                        else:
                            response = f"[{debater.name}: no valid agent]"
                            yield StreamEvent(type=EventType.error, content=response)

                        entry = f"[{debater.name} (Round {round_num + 1})] {response}"
                        transcript.append(entry)
                        yield StreamEvent(type=EventType.text, content=f"\n{entry}\n")

                    except Exception as e:
                        logger.error(f"Debater {debater.name} failed: {e}")
                        err_entry = f"[{debater.name}] Error: {e}"
                        transcript.append(err_entry)
                        yield StreamEvent(type=EventType.error, content=err_entry)

                # Consensus check
                yield StreamEvent(type=EventType.status, content="Checking for consensus...")

                if self.consensus_llm is not None:
                    check = await self.consensus_llm.generate([
                        Message.system(CONSENSUS_CHECK_PROMPT.format(
                            topic=topic,
                            transcript="\n".join(transcript[-8:]),
                        )),
                        Message.user("Has consensus been reached?"),
                    ])
                    check_text = (check.content or "").strip()
                    yield StreamEvent(type=EventType.text, content=f"\n[Consensus Check: {check_text}]\n")

                    if check_text.upper().startswith("CONSENSUS: YES"):
                        yield StreamEvent(type=EventType.state, content="consensus_reached",
                                          data={"state": "consensus", "rounds": round_num + 1})
                        yield StreamEvent(type=EventType.status, content="Consensus reached!")
                        # Extract position if available
                        for line in check_text.split("\n"):
                            if line.upper().startswith("POSITION:"):
                                yield StreamEvent(type=EventType.text,
                                                  content=f"\n[Consensus Position]\n{line[len('POSITION:'):].strip()}\n")
                        break
                else:
                    yield StreamEvent(type=EventType.status, content="(no consensus LLM configured, continuing to next round)")

            else:
                yield StreamEvent(type=EventType.state, content="max_rounds_reached",
                                  data={"state": "max_rounds", "rounds": self.max_rounds})
                yield StreamEvent(type=EventType.status, content="Max debate rounds reached without full consensus")

            yield StreamEvent(type=EventType.state, content="done",
                              data={"state": "done", "rounds": min(round_num + 1, self.max_rounds),
                                    "transcript_lines": len(transcript)})
            yield StreamEvent(type=EventType.done)

        return Stream(_generate())

    def add_debater(
        self,
        name: str,
        agent: Any,
        stance: str = "",
        turn_order: int | None = None,
    ) -> "Debate":
        if turn_order is None:
            turn_order = len(self.debaters)
        self.debaters.append(DebateAgent(name=name, agent=agent, stance=stance, turn_order=turn_order))
        return self
