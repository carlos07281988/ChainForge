"""example/03_core_stream.py — StreamEvent and Stream verification."""
import sys, asyncio
from chainforge.core.stream import StreamEvent, EventType
passed = 0; failed = 0

def check(n, ok):
    global passed, failed
    if ok: passed += 1; print(f"  \u2705 {n}")
    else: failed += 1; print(f"  \u274c {n}")

def test_event_factories():
    e1 = StreamEvent.text("Hello")
    check("e1: text event type", e1.type == EventType.text)
    check("e2: text event content", e1.content == "Hello")
    e2 = StreamEvent.tool_call("get_weather", {"city": "Beijing"}, "c1")
    check("e3: tool_call type", e2.type == EventType.tool_call)
    check("e4: tool_call name", e2.data["name"] == "get_weather")
    check("e5: tool_call id", e2.data["id"] == "c1")
    e3 = StreamEvent.tool_result("get_weather", "Sunny")
    check("e6: tool_result type", e3.type == EventType.tool_result)
    check("e7: tool_result is_error", e3.data["is_error"] == False)
    e4 = StreamEvent.error("Something went wrong")
    check("e8: error type", e4.type == EventType.error)
    check("e9: error content", e4.content == "Something went wrong")
    e5 = StreamEvent.done("Finished")
    check("ea: done type", e5.type == EventType.done)
    check("eb: done content", e5.content == "Finished")
    e6 = StreamEvent.status("processing")
    check("ec: status type", e6.type == EventType.status)
    check("ed: status content", e6.content == "processing")

def test_event_state():
    e = StreamEvent.state_transition("thinking", "Thinking about the problem")
    check("es1: state type", e.type == EventType.state)
    check("es2: state content", e.content == "Thinking about the problem")
    check("es3: state data", e.data.get("state") == "thinking")

def test_stream_collect():
    async def test():
        e1 = StreamEvent.text("Hello")
        e2 = StreamEvent.text(" World")
        e3 = StreamEvent.done()
        async def gen():
            yield e1; yield e2; yield e3
        from chainforge.core.stream import Stream
        s = Stream(gen())
        text = await s.collect_text()
        check("sc1: collect_text", text == "Hello World")
    asyncio.run(test())

def test_stream_collect_list():
    async def test():
        async def gen():
            yield StreamEvent.text("a"); yield StreamEvent.done()
        from chainforge.core.stream import Stream
        s = Stream(gen())
        events = await s.collect()
        check("sc2: collect count", len(events) == 2)
        check("sc3: first event text", events[0].type == EventType.text)
    asyncio.run(test())

def test_stream_error():
    async def test():
        async def gen():
            yield StreamEvent.text("Before")
            yield StreamEvent.error("Oops")
            yield StreamEvent.done()
        from chainforge.core.stream import Stream
        s = Stream(gen())
        events = await s.collect()
        has_error = any(e.type == EventType.error for e in events)
        check("sc4: has error event", has_error)
    asyncio.run(test())

def main():
    print("=" * 58)
    print("  Core Stream \u2014 StreamEvent factories, Stream utilities")
    print("=" * 58)
    test_event_factories(); test_event_state()
    test_stream_collect(); test_stream_collect_list(); test_stream_error()
    print(f"\n  Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    main()
