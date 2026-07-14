"""Tests for conversation serialization."""

import json
import tempfile
from pathlib import Path

import pytest
from chainforge.core.conversation import Conversation
from chainforge.core.message import Message, Role


class TestConversation:
    def test_empty_creation(self):
        conv = Conversation()
        assert conv.message_count == 0
        assert conv.messages == []
        assert conv.metadata == {}

    def test_add_user_message(self):
        conv = Conversation()
        conv.add_user_message("Hello")
        assert conv.message_count == 1
        assert conv.messages[0].role == Role.user
        assert conv.messages[0].content == "Hello"

    def test_add_assistant_message(self):
        conv = Conversation()
        conv.add_assistant_message("Hi there")
        assert conv.messages[0].role == Role.assistant

    def test_add_message_with_string_role(self):
        conv = Conversation()
        conv.add_message("system", "System prompt")
        assert conv.messages[0].role == Role.system

    def test_to_message_list(self):
        conv = Conversation()
        conv.add_user_message("Hello")
        msgs = conv.to_message_list()
        assert len(msgs) == 1
        assert msgs[0].content == "Hello"

    def test_serialize_roundtrip(self):
        conv = Conversation(messages=[
            Message(role=Role.user, content="Hello"),
            Message(role=Role.assistant, content="World"),
        ])
        data = conv.to_dict()
        assert data["version"] == "1.0"
        assert len(data["messages"]) == 2

        restored = Conversation.from_dict(data)
        assert restored.message_count == 2
        assert restored.messages[0].content == "Hello"
        assert restored.messages[0].role == Role.user

    def test_metadata_serialization(self):
        conv = Conversation(metadata={"agent_name": "test", "session": "abc"})
        data = conv.to_dict()
        assert data["metadata"]["agent_name"] == "test"
        restored = Conversation.from_dict(data)
        assert restored.metadata["session"] == "abc"

    def test_save_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chat.json"
            conv = Conversation()
            conv.add_user_message("Hello")
            conv.save(path)
            assert path.exists()
            data = json.loads(path.read_text())
            assert data["messages"][0]["content"] == "Hello"

    def test_load_from_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chat.json"
            original = Conversation()
            original.add_user_message("Save me")
            original.add_assistant_message("Saved!")
            original.save(path)

            restored = Conversation.load(path)
            assert restored.message_count == 2
            assert restored.messages[-1].content == "Saved!"

    def test_load_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            Conversation.load("/nonexistent/chat.json")

    def test_summary_empty(self):
        conv = Conversation()
        assert "(empty conversation)" in conv.summary()

    def test_summary_with_messages(self):
        conv = Conversation()
        conv.add_user_message("What is Python?")
        conv.add_assistant_message("Python is a language.")
        summary = conv.summary()
        assert "Python" in summary
        assert "user" in summary.lower()

    def test_clear(self):
        conv = Conversation()
        conv.add_user_message("Hello")
        assert conv.message_count == 1
        conv.clear()
        assert conv.message_count == 0
        assert conv.last_output == ""


class TestConversationWithAgent:
    @pytest.mark.asyncio
    async def test_run_with_prompt(self):
        from chainforge.testing import MockLLM, MockResponse
        from chainforge.core.agent import Agent

        llm = MockLLM(responses=[MockResponse(content="Hello there!")])
        agent = Agent(llm=llm)
        conv = Conversation()

        stream = await conv.run(agent, "Say hello")
        texts = []
        async for event in stream:
            if hasattr(event, "type") and event.type == "text" and event.content:
                texts.append(event.content)

        assert conv.message_count >= 1
        assert "Hello" in str([m.content for m in conv.messages])

    @pytest.mark.asyncio
    async def test_run_with_existing_messages(self):
        from chainforge.testing import MockLLM, MockResponse
        from chainforge.core.agent import Agent

        conv = Conversation(messages=[
            Message(role=Role.user, content="First message"),
            Message(role=Role.assistant, content="First response"),
        ])

        llm = MockLLM(responses=[MockResponse(content="Second response")])
        agent = Agent(llm=llm)

        stream = await conv.run(agent, "Second message")
        async for event in stream:
            pass

        assert conv.message_count >= 3
