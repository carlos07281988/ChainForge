"""JSON output parser."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from chainforge.parsers.base import ParseResult


class JSONOutputParser(BaseModel):
    """Parse LLM output as JSON.

    Expects the LLM to output valid JSON, optionally wrapped in ```json``` blocks.

    Usage:
        parser = JSONOutputParser()
        result = parser.parse('{"name": "Alice", "age": 30}')
        print(result.parsed)  # {"name": "Alice", "age": 30}
    """

    def parse(self, text: str) -> ParseResult:
        if not text:
            return ParseResult(parsed=None, raw=text, error="Empty text")

        # Try to extract JSON from markdown code blocks
        cleaned = text.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1]
            if "```" in cleaned:
                cleaned = cleaned.split("```")[0]
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1]
            if "```" in cleaned:
                cleaned = cleaned.split("```")[0]

        cleaned = cleaned.strip()
        try:
            parsed = json.loads(cleaned)
            return ParseResult(parsed=parsed, raw=text)
        except json.JSONDecodeError as e:
            return ParseResult(parsed=None, raw=text, error=str(e))

    def format_instructions(self) -> str:
        return "Return your response as valid JSON. Do NOT wrap in markdown code blocks."
