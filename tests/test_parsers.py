"""Tests for output parsers."""
import pytest
from pydantic import BaseModel
from chainforge.parsers import JSONOutputParser, PydanticOutputParser, ParseResult


class TestJSONOutputParser:
    def test_parse_valid(self):
        parser = JSONOutputParser()
        result = parser.parse('{"name": "Alice", "age": 30}')
        assert result.error is None
        assert result.parsed["name"] == "Alice"
        assert result.parsed["age"] == 30

    def test_parse_code_block(self):
        parser = JSONOutputParser()
        result = parser.parse('```json\n{"key": "value"}\n```')
        assert result.error is None
        assert result.parsed["key"] == "value"

    def test_parse_invalid(self):
        parser = JSONOutputParser()
        result = parser.parse("not json")
        assert result.error is not None
        assert result.parsed is None

    def test_empty(self):
        parser = JSONOutputParser()
        result = parser.parse("")
        assert result.error is not None

    def test_format_instructions(self):
        parser = JSONOutputParser()
        assert "JSON" in parser.format_instructions()


class TestPydanticOutputParser:
    def test_parse_valid(self):
        class Person(BaseModel):
            name: str
            age: int

        parser = PydanticOutputParser(pydantic_model=Person)
        result = parser.parse('{"name": "Alice", "age": 30}')
        assert result.error is None
        assert isinstance(result.parsed, Person)
        assert result.parsed.name == "Alice"

    def test_parse_invalid_field(self):
        class Person(BaseModel):
            name: str

        parser = PydanticOutputParser(pydantic_model=Person)
        result = parser.parse('{"name": 123}')
        assert result.error is not None

    def test_format_instructions(self):
        class Simple(BaseModel):
            x: int
        parser = PydanticOutputParser(pydantic_model=Simple)
        instr = parser.format_instructions()
        assert "x" in instr
