"""Base parser types."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class ParseResult(BaseModel):
    """Result of parsing LLM output."""
    parsed: Any = Field(description="Parsed value")
    raw: str = Field(description="Raw text")
    error: str | None = Field(default=None, description="Parse error if any")


class Parser(Protocol):
    """Protocol for output parsers."""

    def parse(self, text: str) -> ParseResult:
        """Parse LLM output text."""
        ...

    def format_instructions(self) -> str:
        """Return instructions for the LLM to format output correctly."""
        ...
