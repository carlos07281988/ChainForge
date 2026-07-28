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
"""StreamBridge — connects upstream and downstream StreamingAgents in real-time."""

from __future__ import annotations

from collections.abc import AsyncIterator

from pydantic import BaseModel, ConfigDict, Field

from chainforge.enterprise.stream_a2a.agent import StreamingAgent
from chainforge.enterprise.stream_a2a.backpressure import BackpressurePolicy
from chainforge.enterprise.stream_a2a.protocol import FrameType, StreamFrame
from chainforge.logging import get_logger

logger = get_logger("stream_a2a.bridge")


class StreamBridge(BaseModel):
    """Real-time bridge between an upstream and a downstream StreamingAgent.

    Each frame produced by the upstream agent is immediately forwarded to
    the downstream agent's consumer.  The bridge supports early termination:
    if the downstream agent sends an interrupt, it is relayed upstream.

    Usage::

        bridge = StreamBridge(backpressure=BackpressurePolicy())
        async for frame in bridge.run(upstream_agent, downstream_agent, "Plan a trip"):
            # frames flow: upstream -> [bridge] -> downstream -> consumer
            ...
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    backpressure: BackpressurePolicy = Field(
        default_factory=BackpressurePolicy, description="Backpressure policy for frame buffering"
    )
    timeout_seconds: float = Field(default=300.0, description="Maximum bridge lifetime in seconds")

    async def run(
        self,
        upstream: StreamingAgent,
        downstream: StreamingAgent,
        prompt: str,
    ) -> AsyncIterator[StreamFrame]:
        """Run the full upstream→downstream pipeline.

        Args:
            upstream: The source agent that produces frames.
            downstream: The target agent that consumes frames from upstream.
            prompt: The initial prompt sent to the upstream agent.

        Yields:
            Every StreamFrame flowing through the bridge (from both agents).
        """
        import asyncio

        buffer: list[StreamFrame] = []
        interrupted = False

        try:
            async for upstream_frame in upstream.start_stream(prompt):
                if interrupted:
                    break

                # Apply backpressure before forwarding
                buffer.append(upstream_frame)
                buffer = self.backpressure.apply(buffer)

                # Yield upstream frame to bridge consumer
                yield upstream_frame

                # Forward every upstream frame to downstream for processing
                await downstream.consume_frame(upstream_frame)

                # Check if upstream is done or errored
                if upstream_frame.frame_type in (FrameType.done, FrameType.error):
                    break

                # Check for interrupt from downstream
                if downstream.is_interrupted:
                    yield upstream.interrupt("downstream-requested-termination")
                    interrupted = True
                    break

        except asyncio.TimeoutError:
            logger.warning("StreamBridge timed out after %.1fs", self.timeout_seconds)
            yield StreamFrame.error_frame(
                agent_id="bridge",
                message=f"Bridge timeout after {self.timeout_seconds}s",
            )

        except Exception as exc:
            logger.error("StreamBridge error: %s", exc)
            yield StreamFrame.error_frame(
                agent_id="bridge",
                message=f"Bridge error: {exc}",
            )
