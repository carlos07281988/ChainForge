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
