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
"""StreamingAgent — wraps a ChainForge Agent for real-time stream-aware communication."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from chainforge.core.agent import Agent
from chainforge.enterprise.stream_a2a.protocol import FrameType, StreamFrame


class StreamingAgent(BaseModel):
    """Wraps a ChainForge Agent with stream-aware send/receive semantics.

    A StreamingAgent translates between the ChainForge internal event model
    and the StreamFrame wire protocol, enabling real-time inter-agent streaming.

    Usage::

        agent = StreamingAgent(agent=my_chainforge_agent, agent_id="assistant-1")
        async for frame in agent.start_stream("What is the weather?"):
            # Each frame is a StreamFrame that can be sent over the wire
            ...
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    agent: Agent = Field(description="The wrapped ChainForge Agent instance")
    agent_id: str = Field(default="streaming-agent", description="Unique ID for this streaming agent")

    # Internal state (not part of serialisation surface)
    _stream_id: str | None = None
    _seq: int = 0
    _interrupted: bool = False
    _inbound_queue: asyncio.Queue[StreamFrame] | None = None

    def _next_seq(self) -> int:
        val = self._seq
        self._seq += 1
        return val

    async def start_stream(self, prompt: str, stream_id: str | None = None) -> AsyncIterator[StreamFrame]:
        """Run the wrapped agent and yield a StreamFrame for every internal event.

        Args:
            prompt: The initial user prompt sent to the agent.
            stream_id: Optional session identifier; auto-generated if omitted.

        Yields:
            StreamFrame instances representing text, tool_call, tool_result, error, and done events.
        """
        self._interrupted = False
        self._seq = 0
        self._stream_id = stream_id or self._stream_id or self.agent_id

        try:
            stream = await self.agent.run(prompt)
            async for event in stream:
                if self._interrupted:
                    break

                match event.type:
                    case "text":
                        yield StreamFrame.text_frame(
                            agent_id=self.agent_id,
                            content=event.content or "",
                            stream_id=self._stream_id,
                            seq=self._next_seq(),
                        )
                    case "tool_call":
                        yield StreamFrame.tool_call_frame(
                            agent_id=self.agent_id,
                            name=event.data.get("name", ""),
                            args=event.data.get("args", {}),
                            stream_id=self._stream_id,
                            seq=self._next_seq(),
                        )
                    case "tool_result":
                        yield StreamFrame.tool_result_frame(
                            agent_id=self.agent_id,
                            name=event.data.get("name", ""),
                            content=event.data.get("content", ""),
                            is_error=event.data.get("is_error", False),
                            stream_id=self._stream_id,
                            seq=self._next_seq(),
                        )
                    case "error":
                        yield StreamFrame.error_frame(
                            agent_id=self.agent_id,
                            message=event.content or "Unknown error",
                            stream_id=self._stream_id,
                            seq=self._next_seq(),
                        )
                    case "done":
                        yield _inherit_payload(event, self.agent_id, self._stream_id, self._next_seq())
                    case _:
                        # Forward unknown event types as a generic frame with full payload
                        yield StreamFrame(
                            frame_type=FrameType.text,
                            agent_id=self.agent_id,
                            stream_id=self._stream_id,
                            seq=self._next_seq(),
                            payload={"content": event.content or "", "event_type": event.type, **event.data},
                        )

        except Exception as exc:
            yield StreamFrame.error_frame(
                agent_id=self.agent_id,
                message=str(exc),
                stream_id=self._stream_id,
                seq=self._next_seq(),
            )

        finally:
            if not self._interrupted:
                yield StreamFrame.done_frame(
                    agent_id=self.agent_id,
                    stream_id=self._stream_id,
                    seq=self._next_seq(),
                )

    async def consume_frame(self, frame: StreamFrame) -> None:
        """Process an incoming frame from another agent.

        Text frames can be used to inject system prompts or context.
        Tool result frames feed tool outputs back into the agent loop.
        Interrupt frames signal early termination.

        Args:
            frame: The incoming frame to process.
        """
        if self._inbound_queue is not None:
            await self._inbound_queue.put(frame)

        if frame.frame_type == FrameType.interrupt:
            self._interrupted = True

    def interrupt(self, reason: str) -> StreamFrame:
        """Send an interrupt frame to upstream agents for early termination.

        Args:
            reason: Human-readable reason for the interruption.

        Returns:
            An interrupt StreamFrame ready to send upstream.
        """
        self._interrupted = True
        return StreamFrame.interrupt_frame(
            agent_id=self.agent_id,
            reason=reason,
            stream_id=self._stream_id or self.agent_id,
        )

    @property
    def is_interrupted(self) -> bool:
        return self._interrupted

    @property
    def current_stream_id(self) -> str | None:
        return self._stream_id


def _inherit_payload(event: Any, agent_id: str, stream_id: str, seq: int) -> StreamFrame:
    """Build a done frame that inherits any extra payload from the internal event."""
    extra: dict[str, Any] = {}
    if hasattr(event, "content") and event.content:
        extra["content"] = event.content
    if hasattr(event, "data") and event.data:
        extra.update(event.data)
    return StreamFrame(
        frame_type=FrameType.done,
        agent_id=agent_id,
        stream_id=stream_id,
        seq=seq,
        payload=extra,
    )
