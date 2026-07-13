"""Tests for the message module."""

import json

from chainforge.core.message import Message, Role, ToolCall, ToolResult


class TestMessage:
    def test_system_message(self):
        msg = Message.system("You are helpful")
        assert msg.role == Role.system
        assert msg.content == "You are helpful"

    def test_user_message(self):
        msg = Message.user("Hello")
        assert msg.role == Role.user
        assert msg.content == "Hello"

    def test_assistant_message(self):
        msg = Message.assistant("Hi there")
        assert msg.role == Role.assistant
        assert msg.content == "Hi there"

    def test_assistant_with_tool_calls(self):
        tc = ToolCall(id="call_1", name="get_weather", args={"city": "Beijing"})
        msg = Message.assistant(tool_calls=[tc])
        assert msg.role == Role.assistant
        assert msg.content is None
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].name == "get_weather"

    def test_tool_result_message(self):
        msg = Message.tool_result("call_1", "get_weather", "Sunny")
        assert msg.role == Role.tool
        assert msg.tool_call_id == "call_1"
        assert msg.content == "Sunny"
        assert msg.name == "get_weather"

    def test_model_dump_openai_system(self):
        msg = Message.system("Be helpful")
        d = msg.model_dump_openai()
        assert d["role"] == "system"
        assert d["content"] == "Be helpful"

    def test_model_dump_openai_user(self):
        msg = Message.user("Hello")
        d = msg.model_dump_openai()
        assert d["role"] == "user"

    def test_model_dump_openai_assistant_text(self):
        msg = Message.assistant("Hello there")
        d = msg.model_dump_openai()
        assert d["role"] == "assistant"
        assert d["content"] == "Hello there"

    def test_model_dump_openai_assistant_tool_calls(self):
        tc = ToolCall(id="call_abc", name="search", args={"q": "test"})
        msg = Message.assistant(tool_calls=[tc])
        d = msg.model_dump_openai()
        assert "tool_calls" in d
        assert d["tool_calls"][0]["function"]["name"] == "search"

    def test_model_dump_openai_tool_result(self):
        msg = Message.tool_result("call_abc", "search", "found it")
        d = msg.model_dump_openai()
        assert d["role"] == "tool"
        assert d["tool_call_id"] == "call_abc"


class TestToolCall:
    def test_tool_call_creation(self):
        tc = ToolCall(id="c1", name="weather", args={"city": "London"})
        assert tc.id == "c1"
        assert tc.name == "weather"
        assert tc.args == {"city": "London"}


class TestToolResult:
    def test_tool_result_defaults(self):
        tr = ToolResult(tool_call_id="c1", name="weather", content="Sunny")
        assert not tr.is_error

    def test_tool_result_error(self):
        tr = ToolResult(tool_call_id="c1", name="weather", content="Failed", is_error=True)
        assert tr.is_error
