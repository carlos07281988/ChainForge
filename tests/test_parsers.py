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
