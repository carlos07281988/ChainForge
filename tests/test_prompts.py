"""Tests for the Prompt Templates module."""

import tempfile
from pathlib import Path

import pytest
from chainforge.prompts import PromptTemplate, ChatPromptTemplate, FewShotPromptTemplate, MessagePlaceholder
from chainforge.core.message import Message, Role


class TestPromptTemplate:
    def test_format_simple(self):
        tmpl = PromptTemplate("Hello, {name}!")
        assert tmpl.format(name="World") == "Hello, World!"

    def test_format_multiple_vars(self):
        tmpl = PromptTemplate("{a} + {b} = {c}")
        assert tmpl.format(a=1, b=2, c=3) == "1 + 2 = 3"

    def test_detect_variables(self):
        tmpl = PromptTemplate("Hello {name}, your {item} is ready")
        assert set(tmpl.input_variables) == {"name", "item"}

    def test_missing_variable(self):
        tmpl = PromptTemplate("Hello {name}!")
        with pytest.raises(KeyError):
            tmpl.format(wrong="World")

    def test_from_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Hello {name} from file!")
            path = f.name
        tmpl = PromptTemplate.from_file(path)
        assert tmpl.format(name="Test") == "Hello Test from file!"
        Path(path).unlink()

    def test_from_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            PromptTemplate.from_file("/nonexistent/template.txt")

    def test_partial(self):
        tmpl = PromptTemplate("{greeting}, {name}!")
        partial = tmpl.partial(greeting="Hello")
        assert "Hello" in partial.format(name="Alice")
        assert partial.input_variables == ["name"]

    def test_add_templates(self):
        t1 = PromptTemplate("Hello {name}")
        t2 = PromptTemplate("How is {name}?")
        combined = t1 + t2
        result = combined.format(name="Alice")
        assert "Alice" in result
        assert combined.input_variables == ["name"]

    def test_str(self):
        tmpl = PromptTemplate("Hello World")
        assert str(tmpl) == "Hello World"

    def test_no_variables(self):
        tmpl = PromptTemplate("Static text")
        assert tmpl.format() == "Static text"
        assert tmpl.input_variables == []


class TestChatPromptTemplate:
    def test_format_messages(self):
        tmpl = ChatPromptTemplate.from_messages([
            ("system", "You are {role}."),
            ("user", "{input}"),
        ])
        messages = tmpl.format_messages(role="helpful", input="Hello")
        assert len(messages) == 2
        assert messages[0].role == Role.system
        assert "helpful" in messages[0].content
        assert messages[1].role == Role.user
        assert messages[1].content == "Hello"

    def test_format_prompt(self):
        tmpl = ChatPromptTemplate.from_messages([
            ("system", "You are helpful."),
            ("user", "Hello"),
        ])
        text = tmpl.format_prompt()
        assert "System:" in text
        assert "User:" in text
        assert "Hello" in text

    def test_with_placeholder(self):
        tmpl = ChatPromptTemplate.from_messages([
            ("system", "You are helpful."),
            MessagePlaceholder(variable_name="history"),
            ("user", "{input}"),
        ])
        messages = tmpl.format_messages(
            input="Hi!",
            history=[
                Message(role=Role.user, content="Previous Q"),
            ],
        )
        assert len(messages) == 3
        assert messages[1].content == "Previous Q"

    def test_empty_placeholder(self):
        tmpl = ChatPromptTemplate.from_messages([
            ("system", "System prompt"),
            MessagePlaceholder(variable_name="history"),
            ("user", "Hello"),
        ])
        messages = tmpl.format_messages()
        assert len(messages) == 2  # No history inserted


class TestFewShotPromptTemplate:
    def test_format(self):
        tmpl = FewShotPromptTemplate(
            examples=[
                {"q": "What is 2+2?", "a": "4"},
                {"q": "What is 3+3?", "a": "6"},
            ],
            example_prompt=PromptTemplate("Q: {q}\nA: {a}"),
            prefix="Math questions:",
            suffix="Q: {input}\nA:",
        )
        result = tmpl.format(input="What is 5+5?")
        assert "Math questions" in result
        assert "What is 2+2?" in result
        assert "5+5" in result

    def test_add_example(self):
        tmpl = FewShotPromptTemplate(
            examples=[],
            example_prompt=PromptTemplate("{q}: {a}"),
            suffix="{input}:",
        )
        tmpl.add_example({"q": "Test", "a": "Result"})
        assert len(tmpl.examples) == 1

    def test_empty_examples(self):
        tmpl = FewShotPromptTemplate(
            examples=[],
            example_prompt=PromptTemplate("{q}"),
            prefix="Start",
            suffix="{input}",
        )
        result = tmpl.format(input="Hello")
        assert "Start" in result
        assert result.endswith("Hello")
