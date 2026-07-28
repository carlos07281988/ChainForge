"""ChainForge Enterprise: Streaming Agent-to-Agent Protocol example.

Usage:
    python examples/enterprise/stream_a2a_example.py
"""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from chainforge.enterprise.stream_a2a import (
    StreamFrame, StreamMessage, StreamProtocol,
    StreamingAgent, StreamBridge, BackpressurePolicy,
)

async def main():
    print("=== Streaming Agent-to-Agent Protocol ===\n")

    # 1. Build stream frames
    frames = [
        StreamFrame(frame_type="text", agent_id="agent-a", stream_id="s1", payload={"content": "Analyzing"}),
        StreamFrame(frame_type="text", agent_id="agent-a", stream_id="s1", payload={"content": " Q3"}),
        StreamFrame(frame_type="text", agent_id="agent-a", stream_id="s1", payload={"content": " data..."}),
        StreamFrame(frame_type="tool_call", agent_id="agent-a", stream_id="s1",
                    payload={"tool_name": "query_db", "arguments": {"query": "Q3 revenue"}}),
        StreamFrame(frame_type="tool_result", agent_id="agent-a", stream_id="s1",
                    payload={"tool_name": "query_db", "result": {"revenue": "$4.2M"}}),
        StreamFrame(frame_type="text", agent_id="agent-a", stream_id="s1", payload={"content": "Q3 revenue: $4.2M"}),
        StreamFrame(frame_type="done", agent_id="agent-a", stream_id="s1", payload={"tokens": 350}),
    ]
    print("1. Stream Frames (7 frames):")
    for f in frames:
        payload_preview = str(f.payload.get("content", str(f.payload)))[:40]
        print(f"   [{f.frame_type}] {f.agent_id}@{f.stream_id}: {payload_preview}")

    # 2. Stream Message -- composed frames
    msg = StreamMessage(frames=frames)
    print(f"\n2. Stream Message:")
    print(f"   Stream: {msg.stream_id}")
    print(f"   Frames: {len(msg.frames)}")
    print(f"   Complete: {msg.is_complete}")
    text = msg.text_content()
    print(f"   Content: {text[:60]}...")

    # 3. Protocol round-trip
    protocol = StreamProtocol()
    encoded = protocol.encode(frames[0])
    decoded = protocol.decode(encoded)
    print(f"\n3. Protocol Round-Trip:")
    print(f"   Encoded: {encoded.decode('utf-8').strip()}")
    print(f"   Decoded: type={decoded.frame_type}, agent={decoded.agent_id}")

    # 4. Backpressure
    bp = BackpressurePolicy(max_buffer=3, strategy="drop_oldest")
    buffer = [frames[0], frames[1], frames[2], frames[3]]  # 4 items, max 3
    result = bp.apply(buffer)
    print(f"\n4. Backpressure (max_buffer=3, drop_oldest):")
    print(f"   Input: {len(frames)} frames sample, buffer=4 -> Output: {len(result)} frames")
    print(f"   Stats: {bp.stats}")

    # 5. Stream message serialization
    serialized = msg.to_json() if hasattr(msg, "to_json") else msg.model_dump()
    deserialized = StreamMessage(**serialized)
    print(f"\n5. Stream Message Serialization:")
    print(f"   Serialized keys: {list(serialized.keys())}")
    print(f"   Deserialized frames: {len(deserialized.frames)}")

if __name__ == "__main__":
    asyncio.run(main())
