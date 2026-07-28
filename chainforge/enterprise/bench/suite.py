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
"""BenchmarkSuite — YAML/JSON-driven benchmark scenario definitions with expectations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


class BenchmarkExpectation(BaseModel):
    """What the correct output should look like."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    tool_calls_include: list[str] = Field(default_factory=list, description="Must call these tools")
    tool_calls_exclude: list[str] = Field(default_factory=list, description="Must NOT call these tools")
    output_contains: list[str] = Field(default_factory=list, description="Output must contain these strings")
    output_not_contains: list[str] = Field(default_factory=list, description="Output must NOT contain these strings")
    max_latency_ms: int | None = None
    max_cost: float | None = None
    min_tool_calls: int | None = None
    max_tool_calls: int | None = None


class BenchmarkScenario(BaseModel):
    """A single benchmark test case."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = ""
    description: str = ""
    input: str = ""
    expect: BenchmarkExpectation = Field(default_factory=BenchmarkExpectation)
    tags: list[str] = Field(default_factory=list)
    weight: float = 1.0  # importance weight


class BenchmarkSuite(BaseModel):
    """A complete benchmark suite."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = ""
    version: str = "1.0"
    description: str = ""
    scenarios: list[BenchmarkScenario] = Field(default_factory=list)

    @classmethod
    def load(cls, path: str) -> "BenchmarkSuite":
        """Load from YAML or JSON file."""
        p = Path(path)
        content = p.read_text()
        if p.suffix in (".yaml", ".yml"):
            data = yaml.safe_load(content)
        else:
            data = json.loads(content)
        scenarios = [BenchmarkScenario(**s) for s in data.get("scenarios", [])]
        return cls(
            name=data.get("name", ""),
            version=data.get("version", "1.0"),
            description=data.get("description", ""),
            scenarios=scenarios,
        )

    def save(self, path: str) -> None:
        """Save to YAML or JSON file."""
        p = Path(path)
        data = self.model_dump()
        if p.suffix in (".yaml", ".yml"):
            p.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True))
        else:
            p.write_text(json.dumps(data, indent=2))

    def to_json(self) -> dict:
        """Serialize to plain dict."""
        return self.model_dump()
