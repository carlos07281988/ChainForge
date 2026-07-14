"""Output Parsers — parse LLM output into structured data.

Provides:
  - JSONOutputParser: extract JSON from LLM responses
  - PydanticOutputParser: parse into Pydantic models
  - CommaSeparatedListOutputParser: parse lists

Usage:
    from chainforge.parsers import JSONOutputParser

    parser = JSONOutputParser()
    result = parser.parse('{"name": "Alice"}')
    print(result.parsed)
"""

from chainforge.parsers.base import ParseResult
from chainforge.parsers.json import JSONOutputParser
from chainforge.parsers.pydantic import PydanticOutputParser

__all__ = ["ParseResult", "JSONOutputParser", "PydanticOutputParser"]
