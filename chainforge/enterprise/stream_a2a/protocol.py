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
"""Stream A2A protocol — frame-based streaming wire format for agent-to-agent communication."""

from __future__ import annotations

import json
import time
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FrameType(str, Enum):
    """Types of frames in the streaming A2A protocol."""
    text = "text"
    tool_call = "tool_call"
    tool_result = "tool_result"
    error = "error"
    done = "done"
    heartbeat = "heartbeat"
    interrupt = "interrupt"


class StreamFrame(BaseModel):
    """A single frame in the streaming protocol — atomic unit of agent communication.

    Each frame carries its type, identity (agent_id, stream_id), a monotonic
    sequence number, and an arbitrary payload.  Frames are ordered within a
    stream and can be reassembled by the receiver.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    frame_type: FrameType = Field(description="Discriminator for frame routing")
    agent_id: str = Field(default="", description="Originating agent identifier")
    stream_id: str = Field(default_factory=lambda: uuid.uuid4().hex, description="Stream session identifier")
    seq: int = Field(default=0, description="Monotonic sequence number within the stream")
    payload: dict[str, Any] = Field(default_factory=dict, description="Arbitrary frame payload")
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp of frame creation")

    @classmethod
    def text_frame(cls, agent_id: str, content: str, stream_id: str = "", seq: int = 0, **extra) -> "StreamFrame":
        return cls(
            frame_type=FrameType.text,
            agent_id=agent_id,
            stream_id=stream_id,
            seq=seq,
            payload={"content": content, **extra},
        )

    @classmethod
    def tool_call_frame(cls, agent_id: str, name: str, args: dict[str, Any], stream_id: str = "", seq: int = 0) -> "StreamFrame":
        return cls(
            frame_type=FrameType.tool_call,
            agent_id=agent_id,
            stream_id=stream_id,
            seq=seq,
            payload={"name": name, "args": args},
        )

    @classmethod
    def tool_result_frame(cls, agent_id: str, name: str, content: str, is_error: bool = False, stream_id: str = "", seq: int = 0) -> "StreamFrame":
        return cls(
            frame_type=FrameType.tool_result,
            agent_id=agent_id,
            stream_id=stream_id,
            seq=seq,
            payload={"name": name, "content": content, "is_error": is_error},
        )

    @classmethod
    def error_frame(cls, agent_id: str, message: str, stream_id: str = "", seq: int = 0) -> "StreamFrame":
        return cls(
            frame_type=FrameType.error,
            agent_id=agent_id,
            stream_id=stream_id,
            seq=seq,
            payload={"message": message},
        )

    @classmethod
    def done_frame(cls, agent_id: str, stream_id: str = "", seq: int = 0, **extra) -> "StreamFrame":
        return cls(
            frame_type=FrameType.done,
            agent_id=agent_id,
            stream_id=stream_id,
            seq=seq,
            payload=extra,
        )

    @classmethod
    def heartbeat_frame(cls, agent_id: str, stream_id: str = "", seq: int = 0) -> "StreamFrame":
        return cls(
            frame_type=FrameType.heartbeat,
            agent_id=agent_id,
            stream_id=stream_id,
            seq=seq,
        )

    @classmethod
    def interrupt_frame(cls, agent_id: str, reason: str, stream_id: str = "", seq: int = 0) -> "StreamFrame":
        return cls(
            frame_type=FrameType.interrupt,
            agent_id=agent_id,
            stream_id=stream_id,
            seq=seq,
            payload={"reason": reason},
        )


class StreamMessage(BaseModel):
    """A composed list of StreamFrames forming a complete agent interaction.

    Think of a StreamMessage as a 'turn' — one agent's response composed of
    multiple frames (text chunks, tool calls, final done marker).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    frames: list[StreamFrame] = Field(default_factory=list, description="Ordered frames in this message")
    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex, description="Unique message identifier")

    @property
    def agent_id(self) -> str:
        return self.frames[0].agent_id if self.frames else ""

    @property
    def stream_id(self) -> str:
        return self.frames[0].stream_id if self.frames else ""

    @property
    def is_complete(self) -> bool:
        """A message is complete when its final frame is 'done' or 'error'."""
        if not self.frames:
            return False
        return self.frames[-1].frame_type in (FrameType.done, FrameType.error)

    def text_content(self) -> str:
        """Extract concatenated text from all text frames."""
        return "".join(f.payload.get("content", "") for f in self.frames if f.frame_type == FrameType.text)


class StreamProtocol:
    """Wire-level protocol for encoding/decoding StreamFrames.

    Uses newline-delimited JSON (NDJSON) so each frame is one line. This
    makes it trivial to stream over WebSockets, SSE, or raw TCP.
    """

    FRAME_DELIMITER = "\n"

    @staticmethod
    def encode(frame: StreamFrame) -> bytes:
        """Encode a single StreamFrame to bytes (JSON line terminated by delimiter)."""
        payload = frame.model_dump()
        return (json.dumps(payload, default=str) + StreamProtocol.FRAME_DELIMITER).encode("utf-8")

    @staticmethod
    def decode(line: bytes) -> StreamFrame:
        """Decode a single JSON line back into a StreamFrame."""
        data = json.loads(line.decode("utf-8"))
        return StreamFrame(**data)

    @classmethod
    def encode_message(cls, message: StreamMessage) -> bytes:
        """Encode an entire StreamMessage as NDJSON."""
        return b"".join(cls.encode(frame) for frame in message.frames)

    @classmethod
    def decode_message(cls, raw: bytes) -> StreamMessage:
        """Decode NDJSON bytes back into a StreamMessage."""
        lines = raw.decode("utf-8").strip().split(cls.FRAME_DELIMITER)
        frames = [cls.decode(line.encode("utf-8")) for line in lines if line]
        return StreamMessage(frames=frames)

    @staticmethod
    def protocol_version() -> str:
        return "chainforge-stream-a2a-v1"
