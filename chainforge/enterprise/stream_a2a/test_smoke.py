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
"""Smoke test for Phase 33-2: Streaming Agent-to-Agent Protocol.

Verifies:
1. StreamFrame construction and serialization round-trip
2. StreamProtocol encode/decode
3. StreamMessage composition
4. BackpressurePolicy strategies
5. End-to-end: 2 StreamingAgents connected via StreamBridge
"""

from __future__ import annotations

import asyncio

from chainforge.core.agent import Agent
from chainforge.core.llm import LLMResponse
from chainforge.enterprise.stream_a2a import (
    BackpressurePolicy,
    StreamBridge,
    StreamFrame,
    StreamingAgent,
    StreamMessage,
    StreamProtocol,
)
from chainforge.enterprise.stream_a2a.backpressure import BackpressureStrategy
from chainforge.enterprise.stream_a2a.protocol import FrameType


# ── Mock LLM for testing (no real API calls) ────────────────────────────────


class MockLLM:
    """Fake LLM that returns canned responses for smoke testing.

    Duck-types the chainforge.core.llm.LLM protocol — not a subclass
    because LLM is a Protocol, not a BaseModel.
    """

    model: str = "mock/test"

    def __init__(self, responses: list[str] | None = None):
        self._responses = responses or ["Hello from mock agent."]
        self._index = 0

    @property
    def capabilities(self) -> set[str]:
        return {"chat", "streaming"}

    async def generate(self, messages, tools=None, **kwargs):
        text = self._responses[self._index % len(self._responses)]
        self._index += 1
        return LLMResponse(content=text, finish_reason="stop", model=self.model)

    async def stream_generate(self, messages, tools=None, **kwargs):
        text = self._responses[self._index % len(self._responses)]
        self._index += 1
        yield LLMResponse(content=text[: len(text) // 2], finish_reason=None, model=self.model)
        yield LLMResponse(content=text[len(text) // 2 :], finish_reason="stop", model=self.model)


# ── Test Helpers ────────────────────────────────────────────────────────────


def test_frame_construction():
    """Verify all frame factory methods produce correct FrameType."""
    agent_id = "test-agent-1"
    sid = "abc123"

    tf = StreamFrame.text_frame(agent_id, "hello", sid)
    assert tf.frame_type == FrameType.text
    assert tf.payload["content"] == "hello"

    tc = StreamFrame.tool_call_frame(agent_id, "search", {"q": "test"}, sid)
    assert tc.frame_type == FrameType.tool_call
    assert tc.payload["name"] == "search"

    tr = StreamFrame.tool_result_frame(agent_id, "search", "found", stream_id=sid)
    assert tr.frame_type == FrameType.tool_result
    assert tr.payload["content"] == "found"

    err = StreamFrame.error_frame(agent_id, "boom", sid)
    assert err.frame_type == FrameType.error
    assert "boom" in err.payload["message"]

    done = StreamFrame.done_frame(agent_id, sid)
    assert done.frame_type == FrameType.done

    hb = StreamFrame.heartbeat_frame(agent_id, sid)
    assert hb.frame_type == FrameType.heartbeat

    interrupt = StreamFrame.interrupt_frame(agent_id, "timeout", sid)
    assert interrupt.frame_type == FrameType.interrupt
    assert interrupt.payload["reason"] == "timeout"

    print("  PASS: frame_construction")


def test_protocol_round_trip():
    """Verify a StreamFrame survives encode → decode without corruption."""
    frame = StreamFrame.text_frame("agent-x", "hello world", stream_id="s1", seq=42)
    raw = StreamProtocol.encode(frame)
    decoded = StreamProtocol.decode(raw.decode("utf-8").strip().encode("utf-8"))

    assert decoded.frame_type == frame.frame_type
    assert decoded.agent_id == frame.agent_id
    assert decoded.stream_id == frame.stream_id
    assert decoded.seq == frame.seq
    assert decoded.payload == frame.payload

    print("  PASS: protocol_round_trip")


def test_stream_message():
    """Verify StreamMessage composition and properties."""
    frames = [
        StreamFrame.text_frame("a1", "Part 1", stream_id="s1", seq=0),
        StreamFrame.text_frame("a1", "Part 2", stream_id="s1", seq=1),
        StreamFrame.done_frame("a1", stream_id="s1", seq=2),
    ]
    msg = StreamMessage(frames=frames)
    assert msg.is_complete
    assert msg.text_content() == "Part 1Part 2"
    assert msg.agent_id == "a1"
    assert msg.stream_id == "s1"

    # Round-trip via StreamProtocol
    raw = StreamProtocol.encode_message(msg)
    msg2 = StreamProtocol.decode_message(raw)
    assert len(msg2.frames) == 3
    assert msg2.is_complete

    print("  PASS: stream_message")


def test_backpressure_policy():
    """Verify all three backpressure strategies behave correctly."""
    # drop_oldest
    policy = BackpressurePolicy(max_buffer=3, strategy=BackpressureStrategy.drop_oldest)
    buffer = [
        StreamFrame.text_frame("a", f"f{i}", seq=i) for i in range(5)
    ]
    result = policy.apply(buffer)
    assert len(result) == 3
    assert result[0].seq == 2  # oldest dropped
    assert policy.stats["dropped_frames"] == 2

    # drop_newest
    policy2 = BackpressurePolicy(max_buffer=3, strategy=BackpressureStrategy.drop_newest)
    buffer2 = [
        StreamFrame.text_frame("a", f"f{i}", seq=i) for i in range(5)
    ]
    result2 = policy2.apply(buffer2)
    assert len(result2) == 3
    assert result2[-1].seq == 2  # newest dropped
    assert policy2.stats["dropped_frames"] == 2

    # block
    policy3 = BackpressurePolicy(max_buffer=3, strategy=BackpressureStrategy.block)
    buffer3 = [
        StreamFrame.text_frame("a", f"f{i}", seq=i) for i in range(5)
    ]
    try:
        policy3.apply(buffer3)
        assert False, "Should have raised RuntimeError"
    except RuntimeError:
        pass
    assert policy3.stats["blocked_count"] == 1

    # under-limit no-op
    policy4 = BackpressurePolicy(max_buffer=10, strategy=BackpressureStrategy.drop_oldest)
    buffer4 = [StreamFrame.text_frame("a", "f0", seq=0)]
    result4 = policy4.apply(buffer4)
    assert len(result4) == 1
    assert policy4.stats["dropped_frames"] == 0

    print("  PASS: backpressure_policy")


async def test_end_to_end_bridge():
    """2 StreamingAgents connected via StreamBridge — verify frame flow."""

    # Upstream agent produces text + done
    upstream_agent = Agent(
        llm=MockLLM(responses=["Analysis: market trends show growth in Q3."]),
        system_prompt="You are a data analyst.",
    )
    upstream = StreamingAgent(agent=upstream_agent, agent_id="analyst")

    # Downstream agent processes and reflects
    downstream_agent = Agent(
        llm=MockLLM(responses=["Summary: positive outlook for Q3."]),
        system_prompt="You are a summarizer.",
    )
    downstream = StreamingAgent(agent=downstream_agent, agent_id="summarizer")

    bp = BackpressurePolicy(max_buffer=128, strategy=BackpressureStrategy.drop_oldest)
    bridge = StreamBridge(backpressure=bp)

    frames = []
    async for frame in bridge.run(upstream, downstream, "Analyze Q3 market trends"):
        frames.append(frame)

    # We should have frames from the upstream agent
    assert len(frames) > 0, "Bridge should produce at least one frame"

    # First frame should be text
    text_frames = [f for f in frames if f.frame_type == FrameType.text]
    assert len(text_frames) >= 1, f"Expected text frames, got {[f.frame_type for f in frames]}"

    # Last frames should include done
    done_frames = [f for f in frames if f.frame_type == FrameType.done]
    assert len(done_frames) >= 1, "Expected a done frame from upstream"

    # Verify agent identity on frames
    agent_ids = {f.agent_id for f in frames}
    assert "analyst" in agent_ids, f"Expected 'analyst' frames, got {agent_ids}"

    # No error frames
    error_frames = [f for f in frames if f.frame_type == FrameType.error]
    assert len(error_frames) == 0, f"Unexpected error frames: {[e.payload for e in error_frames]}"

    print(f"  PASS: end_to_end_bridge ({len(frames)} frames: {[f.frame_type.value for f in frames]})")


async def test_interrupt_flow():
    """Verify downstream can interrupt upstream."""
    upstream_agent = Agent(
        llm=MockLLM(responses=["Part 1.", "Part 2.", "Part 3.", "Part 4."]),
        system_prompt="You are a verbose agent.",
    )
    upstream = StreamingAgent(agent=upstream_agent, agent_id="verbose")

    downstream_agent = Agent(
        llm=MockLLM(responses=["Short summary."]),
        system_prompt="You are concise.",
    )
    downstream = StreamingAgent(agent=downstream_agent, agent_id="concise")

    bridge = StreamBridge(backpressure=BackpressurePolicy(max_buffer=64))

    frames = []
    async for frame in bridge.run(upstream, downstream, "Tell me a long story"):
        frames.append(frame)
        # Interrupt from downstream after first text frame
        if frame.frame_type == FrameType.text:
            downstream.interrupt("already enough info")

    # Should have an interrupt frame
    interrupt_frames = [f for f in frames if f.frame_type == FrameType.interrupt]
    assert len(interrupt_frames) >= 1, f"Expected interrupt frame, got {[f.frame_type.value for f in frames]}"

    print(f"  PASS: interrupt_flow ({len(frames)} frames)")


# ── Main ────────────────────────────────────────────────────────────────────


def main():
    print("Phase 33-2 Smoke Test: Streaming Agent-to-Agent Protocol\n")

    print("[1] Frame Construction")
    test_frame_construction()

    print("[2] Protocol Round-Trip")
    test_protocol_round_trip()

    print("[3] StreamMessage")
    test_stream_message()

    print("[4] Backpressure Policy")
    test_backpressure_policy()

    print("[5] End-to-End Bridge")
    asyncio.run(test_end_to_end_bridge())

    print("[6] Interrupt Flow")
    asyncio.run(test_interrupt_flow())

    print("\n  All 6 tests PASSED.")


if __name__ == "__main__":
    main()
