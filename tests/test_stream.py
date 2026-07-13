"""Tests for the stream module."""

import pytest

from chainforge.core.stream import StreamEvent, EventType


class TestStreamEvent:
    def test_text_event(self):
        e = StreamEvent.text("hello")
        assert e.type == EventType.text
        assert e.content == "hello"
        assert e.data == {}

    def test_tool_call_event(self):
        e = StreamEvent.tool_call("get_weather", {"city": "Beijing"}, id="c1")
        assert e.type == EventType.tool_call
        assert e.data["name"] == "get_weather"
        assert e.data["id"] == "c1"

    def test_tool_result_event(self):
        e = StreamEvent.tool_result("get_weather", "Sunny")
        assert e.type == EventType.tool_result
        assert e.data["is_error"] is False

    def test_error_event(self):
        e = StreamEvent.error("something went wrong")
        assert e.type == EventType.error
        assert e.content == "something went wrong"

    def test_done_event(self):
        e = StreamEvent.done()
        assert e.type == EventType.done

    def test_status_event(self):
        e = StreamEvent.status("processing")
        assert e.type == EventType.status
        assert e.content == "processing"


class TestEventType:
    def test_enum_values(self):
        assert EventType.text.value == "text"
        assert EventType.tool_call.value == "tool_call"
        assert EventType.tool_result.value == "tool_result"
        assert EventType.error.value == "error"
        assert EventType.done.value == "done"
        assert EventType.status.value == "status"
