"""example/15_tracing.py — Tracing primitives verification."""
import sys, time
from chainforge.tracing import Span, Trace, Tracer
passed = 0; failed = 0

def check(n, ok):
    global passed, failed
    if ok: passed += 1; print(f"  \u2705 {n}")
    else: failed += 1; print(f"  \u274c {n}")

def test_span_defaults():
    span = Span(name="test_span")
    check("sp1: name", span.name == "test_span")
    check("sp2: has id", len(span.id) > 0)
    check("sp3: start_time set", span.start_time > 0)
    check("sp4: end_time None", span.end_time is None)
    check("sp5: no parent", span.parent_id is None)

def test_span_with_parent():
    span = Span(name="child", parent_id="parent_1")
    check("sp6: parent id", span.parent_id == "parent_1")

def test_span_duration():
    span = Span(name="test")
    check("sp7: duration positive", span.duration_ms > 0)
    span.end_time = span.start_time + 1.0
    check("sp8: duration ~1s", abs(span.duration_ms - 1000) < 50)

def test_span_attributes():
    span = Span(name="test", attributes={"key": "value"})
    check("sp9: gets attribute", span.attributes["key"] == "value")

def test_span_events():
    span = Span(name="test")
    span.events.append({"name": "start", "timestamp": time.time()})
    check("sp10: has event", len(span.events) == 1)

def main():
    print("=" * 58)
    print("  Tracing \u2014 Span primitives")
    print("=" * 58)
    test_span_defaults(); test_span_with_parent()
    test_span_duration(); test_span_attributes()
    test_span_events()
    print(f"\n  Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    main()
