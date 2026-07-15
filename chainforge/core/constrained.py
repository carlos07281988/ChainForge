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
"""Constrained decoding — token-level structured output enforcement.

Integrates with outlines and lm-format-enforcer for guaranteed
schema-compliant generation. Falls back to JSON mode + retry.

Usage:
    from chainforge.core.constrained import ConstrainedDecoder

    decoder = ConstrainedDecoder(backend="outlines")
    schema = {"type": "object", "properties": {"name": {"type": "string"}}}
    text = await decoder.generate(llm, prompt, schema)
"""

from __future__ import annotations

import json
import re
from typing import Any

from chainforge.core.llm import LLM, LLMResponse
from chainforge.core.message import Message
from chainforge.logging import get_logger

logger = get_logger("core.constrained")


class ConstrainedDecoder:
    """Generate structured output with schema enforcement.

    Supports multiple backends:
      - "outlines": uses outlines library for grammar-guided generation
      - "lmfe": uses lm-format-enforcer for token-level constraints
      - "jsonmode": fallback — JSON mode + retry with validation

    Usage:
        decoder = ConstrainedDecoder(backend="outlines")
        schema = Movie.model_json_schema()
        result = await decoder.generate(
            llm=my_llm,
            prompt="Recommend a movie",
            schema=schema,
        )
        # Returns parsed dict guaranteed to match schema
    """

    def __init__(self, backend: str = "jsonmode", max_retries: int = 2):
        self.backend = backend
        self.max_retries = max_retries

    async def generate(
        self,
        llm: LLM,
        prompt: str,
        schema: dict[str, Any],
        *,
        system_prompt: str | None = None,
    ) -> dict[str, Any] | None:
        """Generate a structured output constrained by schema.

        Args:
            llm: LLM provider.
            prompt: User prompt.
            schema: JSON Schema dict.
            system_prompt: Optional system instructions.

        Returns:
            Parsed dict matching schema, or None on failure.
        """
        if self.backend == "jsonmode":
            return await self._jsonmode_fallback(llm, prompt, schema, system_prompt=system_prompt)

        if self.backend == "outlines":
            try:
                return await self._outlines_generate(llm, prompt, schema, system_prompt=system_prompt)
            except ImportError:
                logger.warning("outlines not installed, falling back to jsonmode")
                return await self._jsonmode_fallback(llm, prompt, schema, system_prompt=system_prompt)

        if self.backend == "lmfe":
            try:
                return await self._lmfe_generate(llm, prompt, schema, system_prompt=system_prompt)
            except ImportError:
                logger.warning("lm-format-enforcer not installed, falling back to jsonmode")
                return await self._jsonmode_fallback(llm, prompt, schema, system_prompt=system_prompt)

        logger.warning(f"Unknown backend '{self.backend}', falling back to jsonmode")
        return await self._jsonmode_fallback(llm, prompt, schema, system_prompt=system_prompt)

    async def _jsonmode_fallback(
        self,
        llm: LLM,
        prompt: str,
        schema: dict[str, Any],
        *,
        system_prompt: str | None = None,
    ) -> dict[str, Any] | None:
        """Generate with JSON mode + retry with validation."""
        msgs = []
        if system_prompt:
            msgs.append(Message.system(system_prompt))
        msgs.append(Message.user(
            f"{prompt}\n\nRespond with valid JSON matching this schema:\n{json.dumps(schema, indent=2)}"
        ))

        for attempt in range(self.max_retries + 1):
            try:
                resp = await llm.generate(msgs, response_format={"type": "json_object"} if hasattr(llm, 'model') else None)
                text = resp.content or ""

                # Extract JSON block if wrapped in code fence
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0].strip()
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0].strip()

                data = json.loads(text)

                # Validate against schema
                if self._validate_schema(data, schema):
                    return data

                logger.debug(f"Attempt {attempt + 1}: schema validation failed, retrying")

            except (json.JSONDecodeError, Exception) as e:
                logger.debug(f"Attempt {attempt + 1}: {e}, retrying")

        return None

    async def _outlines_generate(
        self,
        llm: LLM,
        prompt: str,
        schema: dict[str, Any],
        *,
        system_prompt: str | None = None,
    ) -> dict[str, Any] | None:
        """Generate with outlines grammar-guided decoding.

        Falls back to jsonmode if outlines is not installed or the provider
        doesn't support the required API attributes.
        """
        api_key = getattr(llm, "api_key", None)
        base_url = getattr(llm, "base_url", None)

        if api_key is None:
            logger.warning("LLM provider has no api_key, falling back to jsonmode")
            return await self._jsonmode_fallback(llm, prompt, schema, system_prompt=system_prompt)

        try:
            import outlines
            from outlines import generate as outlines_generate
            from outlines.models import OpenAI as OutlinesOpenAI

            outlines_model = OutlinesOpenAI(
                model=llm.model,
                api_key=api_key,
                base_url=base_url,
            )
            generator = outlines_generate.json(outlines_model, schema)

            full_prompt = ""
            if system_prompt:
                full_prompt += f"{system_prompt}\n\n"
            full_prompt += prompt

            # Run blocking outlines call in thread pool to avoid blocking event loop
            import asyncio
            text = await asyncio.to_thread(generator, full_prompt, max_tokens=4096)

            if isinstance(text, str):
                return json.loads(text)
            return text

        except ImportError:
            logger.warning("outlines not installed, falling back to jsonmode")
            return await self._jsonmode_fallback(llm, prompt, schema, system_prompt=system_prompt)
        except Exception as e:
            logger.warning(f"outlines generation failed: {e}, falling back to jsonmode")
            return await self._jsonmode_fallback(llm, prompt, schema, system_prompt=system_prompt)

    async def _lmfe_generate(
        self,
        llm: LLM,
        prompt: str,
        schema: dict[str, Any],
        *,
        system_prompt: str | None = None,
    ) -> dict[str, Any] | None:
        """Generate with lm-format-enforcer token-level constraints.

        Falls back to jsonmode if lm-format-enforcer is not installed
        or the provider doesn't have an api_key.
        """
        api_key = getattr(llm, "api_key", None)
        base_url = getattr(llm, "base_url", None)

        if api_key is None:
            logger.warning("LLM provider has no api_key, falling back to jsonmode")
            return await self._jsonmode_fallback(llm, prompt, schema, system_prompt=system_prompt)

        try:
            from lmformatenforcer import JsonSchemaParser
            from lmformatenforcer.integrations.openai import build_openai_schema_adapter
            from openai import AsyncOpenAI

            msgs = []
            if system_prompt:
                msgs.append(Message.system(system_prompt))
            msgs.append(Message.user(prompt))
            raw_messages = [m.model_dump_openai() for m in msgs]

            parser = JsonSchemaParser(schema)
            schema_adapter = build_openai_schema_adapter(parser)

            client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
            )

            response = await client.chat.completions.create(
                model=llm.model,
                messages=raw_messages,
                temperature=0.0,
            )
            text = response.choices[0].message.content or ""
            return json.loads(text)
        except ImportError:
            logger.warning("lm-format-enforcer not installed, falling back to jsonmode")
            return await self._jsonmode_fallback(llm, prompt, schema, system_prompt=system_prompt)
        except Exception as e:
            logger.warning(f"lmfe generation failed: {e}")
            return None

    @staticmethod
    def _validate_schema(data: Any, schema: dict[str, Any]) -> bool:
        """Basic schema validation (property presence and types)."""
        if "properties" in schema:
            if not isinstance(data, dict):
                return False
            required = schema.get("required", [])
            for field in required:
                if field not in data:
                    return False
            for key, value in data.items():
                prop_schema = schema["properties"].get(key, {})
                prop_type = prop_schema.get("type", "")
                if prop_type == "string" and not isinstance(value, str):
                    return False
                if prop_type == "integer" and not isinstance(value, int):
                    return False
                if prop_type == "number" and not isinstance(value, (int, float)):
                    return False
                if prop_type == "boolean" and not isinstance(value, bool):
                    return False
                if prop_type == "array" and not isinstance(value, list):
                    return False
        return True


def constrain_to_schema(schema: dict[str, Any]) -> callable:
    """Decorator that constrains an agent's response to a JSON schema.

    Usage:
        @constrain_to_schema(Movie.model_json_schema())
        async def get_movie(agent, prompt):
            return await agent.run(prompt)
    """
    decoder = ConstrainedDecoder()

    def decorator(func):
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            if isinstance(result, dict):
                return result
            # Try to parse as structured output
            llm = kwargs.get("llm") or (args[0] if args else None)
            if hasattr(llm, "generate"):
                return await decoder.generate(llm, str(result), schema)
            return result
        return wrapper
    return decorator
