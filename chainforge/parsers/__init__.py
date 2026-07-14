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
