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
"""Backpressure policy for streaming A2A — guards against unbounded buffer growth."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from chainforge.enterprise.stream_a2a.protocol import StreamFrame


class BackpressureStrategy(str, Enum):
    """Strategies for handling buffer overflow."""
    drop_oldest = "drop_oldest"
    drop_newest = "drop_newest"
    block = "block"


class BackpressurePolicy(BaseModel):
    """Configurable backpressure policy for StreamBridge frame buffering.

    When the buffer exceeds max_buffer frames, the chosen strategy is applied:

    - **drop_oldest**: Remove the oldest frames to make room (prefer recency).
    - **drop_newest**: Drop incoming frames (prefer completeness of early frames).
    - **block**: Raise an error to block further frame production (strict mode).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    max_buffer: int = Field(default=256, description="Maximum number of buffered frames before backpressure triggers")
    strategy: BackpressureStrategy = Field(
        default=BackpressureStrategy.block, description="Action to take when buffer is full"
    )

    # Counters (reset per stream)
    _dropped_frames: int = 0
    _blocked_count: int = 0
    _buffer_size: int = 0

    def apply(self, buffer: list[StreamFrame]) -> list[StreamFrame]:
        """Enforce the backpressure policy on the given buffer.

        Args:
            buffer: The current frame buffer (may be mutated in-place).

        Returns:
            The buffer after applying the policy.

        Raises:
            RuntimeError: If the strategy is ``block`` and the buffer is full.
        """
        self._buffer_size = len(buffer)

        if len(buffer) <= self.max_buffer:
            return buffer

        excess = len(buffer) - self.max_buffer

        match self.strategy:
            case BackpressureStrategy.drop_oldest:
                buffer = buffer[excess:]
                self._dropped_frames += excess
                return buffer

            case BackpressureStrategy.drop_newest:
                buffer = buffer[: self.max_buffer]
                self._dropped_frames += excess
                return buffer

            case BackpressureStrategy.block:
                self._blocked_count += 1
                raise RuntimeError(
                    f"Stream buffer full ({len(buffer)}/{self.max_buffer}). "
                    f"Policy is 'block' — upstream production halted."
                )

        return buffer

    @property
    def stats(self) -> dict[str, Any]:
        """Return current backpressure statistics."""
        return {
            "buffer_size": self._buffer_size,
            "max_buffer": self.max_buffer,
            "dropped_frames": self._dropped_frames,
            "blocked_count": self._blocked_count,
            "strategy": self.strategy.value,
        }

    def reset_stats(self) -> None:
        """Reset counters for a new stream session."""
        self._dropped_frames = 0
        self._blocked_count = 0
        self._buffer_size = 0
