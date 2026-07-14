# Copyright 2024 ChainForge Contributors
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
"""Tests for structured output module."""

import pytest
from pydantic import BaseModel

from chainforge.core.structured_output import model_to_json_schema, parse_structured_response


class WeatherResponse(BaseModel):
    city: str
    temperature: float
    condition: str


class TestModelToJsonSchema:
    def test_basic_schema(self):
        schema = model_to_json_schema(WeatherResponse)
        assert "properties" in schema
        assert "city" in schema["properties"]
        assert "temperature" in schema["properties"]

    def test_schema_types(self):
        schema = model_to_json_schema(WeatherResponse)
        assert schema["properties"]["temperature"]["type"] == "number"
        assert schema["properties"]["city"]["type"] == "string"


class TestParseStructuredResponse:
    def test_direct_json(self):
        result = parse_structured_response(
            '{"city": "Beijing", "temperature": 28.0, "condition": "Sunny"}',
            WeatherResponse,
        )
        assert isinstance(result, WeatherResponse)
        assert result.city == "Beijing"
        assert result.temperature == 28.0

    def test_code_block_json(self):
        result = parse_structured_response(
            "Here is the weather:\n```json\n{\"city\": \"London\", \"temperature\": 15.5, \"condition\": \"Cloudy\"}\n```",
            WeatherResponse,
        )
        assert result.city == "London"
        assert result.temperature == 15.5

    def test_invalid_response(self):
        with pytest.raises(ValueError):
            parse_structured_response("This is not JSON at all", WeatherResponse)

    def test_empty_response(self):
        with pytest.raises(ValueError):
            parse_structured_response("", WeatherResponse)
