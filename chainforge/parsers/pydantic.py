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
"""Pydantic output parser — parse LLM output into Pydantic models."""

from __future__ import annotations

import json
from typing import Any, Type

from pydantic import BaseModel, Field

from chainforge.parsers.base import ParseResult
from chainforge.parsers.json import JSONOutputParser


class PydanticOutputParser(BaseModel):
    """Parse LLM output into a Pydantic model instance.

    Usage:
        class Person(BaseModel):
            name: str
            age: int

        parser = PydanticOutputParser(pydantic_model=Person)
        result = parser.parse('{"name": "Alice", "age": 30}')
        print(result.parsed)  # Person(name='Alice', age=30)
    """

    pydantic_model: Type = Field(description="Pydantic model class")
    _json_parser: Any = None

    def __init__(self, pydantic_model: Type, **kwargs):
        super().__init__(pydantic_model=pydantic_model, **kwargs)
        self._json_parser = JSONOutputParser()

    def parse(self, text: str) -> ParseResult:
        json_result = self._json_parser.parse(text)
        if json_result.error:
            return json_result
        if not isinstance(json_result.parsed, dict):
            return ParseResult(parsed=None, raw=text, error="JSON result is not a dict")
        try:
            instance = self.pydantic_model(**json_result.parsed)
            return ParseResult(parsed=instance, raw=text)
        except Exception as e:
            return ParseResult(parsed=None, raw=text, error=str(e))

    def format_instructions(self) -> str:
        schema = self.pydantic_model.model_json_schema()
        return f"Return a JSON object matching this schema:\n{json.dumps(schema, indent=2)}"
