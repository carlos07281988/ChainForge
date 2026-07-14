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
"""EvalSuite — a collection of test cases with loading/saving support."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from chainforge.eval.case import EvalCase


class EvalSuite(BaseModel):
    """A named collection of evaluation test cases."""

    name: str = Field(description="Suite name")
    description: str = Field(default="", description="Suite description")
    cases: list[EvalCase] = Field(default_factory=list, description="Test cases")
    tags: list[str] = Field(default_factory=list, description="Suite-level tags")

    def add(self, case: EvalCase) -> EvalSuite:
        self.cases.append(case)
        return self

    def by_tag(self, tag: str) -> list[EvalCase]:
        return [c for c in self.cases if tag in c.tags]

    def by_name(self, name: str) -> EvalCase | None:
        for c in self.cases:
            if c.name == name:
                return c
        return None

    def filter(self, tags: list[str] | None = None, names: list[str] | None = None) -> EvalSuite:
        cases = self.cases
        if tags:
            cases = [c for c in cases if any(t in c.tags for t in tags)]
        if names:
            cases = [c for c in cases if c.name in names]
        return EvalSuite(name=self.name, description=self.description, cases=cases, tags=self.tags)

    @classmethod
    def from_json(cls, path: str | Path) -> EvalSuite:
        data = json.loads(Path(path).read_text())
        return cls.model_validate(data)

    @classmethod
    def from_json_str(cls, text: str) -> EvalSuite:
        data = json.loads(text)
        return cls.model_validate(data)

    def to_json(self, path: str | Path | None = None) -> str:
        text = self.model_dump_json(indent=2)
        if path:
            Path(path).write_text(text)
        return text

    @property
    def total_weight(self) -> float:
        return sum(c.weight for c in self.cases)

    @property
    def case_count(self) -> int:
        return len(self.cases)

    def __len__(self) -> int:
        return len(self.cases)

    def __iter__(self):
        return iter(self.cases)

    def __getitem__(self, idx):
        return self.cases[idx]
