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
"""Structured output — constrain LLM responses to a Pydantic model.

Provides response_model support for the Agent and LLM layers.
Uses JSON mode + tool calling under the hood for reliable parsing.
"""

from __future__ import annotations

import json
from typing import Any, get_origin, get_args

from pydantic import BaseModel
from pydantic.json_schema import GenerateJsonSchema


def model_to_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Convert a Pydantic model to a JSON Schema (for tool parameters)."""
    schema = model.model_json_schema(schema_generator=GenerateJsonSchema)
    # Flatten $defs into properties for simpler inline usage
    definitions = schema.pop("$defs", {})
    for prop_name, prop_value in schema.get("properties", {}).items():
        ref = prop_value.get("$ref", "")
        if ref:
            def_key = ref.split("/")[-1]
            if def_key in definitions:
                schema["properties"][prop_name] = definitions[def_key]
    return schema


def parse_structured_response(
    content: str,
    response_model: type[BaseModel],
    llm_provider: str = "openai",
) -> BaseModel:
    """Parse LLM text response into a Pydantic model.

    Tries multiple strategies:
    1. Direct json.loads
    2. Extract JSON from markdown code blocks
    3. For OpenAI, handle tool_call-style responses
    """
    # Strategy 1: direct parse
    content_stripped = content.strip() if content else ""
    if content_stripped:
        try:
            data = json.loads(content_stripped)
            return response_model.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            pass

        # Strategy 2: extract from code block
        if "```json" in content_stripped:
            json_str = content_stripped.split("```json")[1].split("```")[0].strip()
            try:
                data = json.loads(json_str)
                return response_model.model_validate(data)
            except (json.JSONDecodeError, ValueError):
                pass
        elif "```" in content_stripped:
            json_str = content_stripped.split("```")[1].split("```")[0].strip()
            try:
                data = json.loads(json_str)
                return response_model.model_validate(data)
            except (json.JSONDecodeError, ValueError):
                pass

    # Strategy 3: fallback — try to find JSON-like content
    import re
    matches = re.findall(r'\{[^{}]*\}', content_stripped)
    for m in matches:
        try:
            data = json.loads(m)
            return response_model.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            continue

    raise ValueError(
        f"Could not parse LLM response into {response_model.__name__}. "
        f"Response was: {content[:200]}"
    )
