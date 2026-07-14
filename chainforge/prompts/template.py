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
"""PromptTemplate — variable injection, template loading, composition."""

from __future__ import annotations

import string
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class PromptTemplate(BaseModel):
    """A parameterized prompt template with ``{variable}`` syntax.

    Usage:
        tmpl = PromptTemplate("Hello, {name}! Today is {day}.")
        result = tmpl.format(name="Alice", day="Monday")
        # "Hello, Alice! Today is Monday."
    """

    template: str = Field(description="Template string with {variable} placeholders")
    input_variables: list[str] = Field(default_factory=list, description="Variable names (auto-detected if empty)")

    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, template: str, **kwargs):
        super().__init__(template=template, **kwargs)
        if not self.input_variables:
            self.input_variables = self._detect_variables()

    def _detect_variables(self) -> list[str]:
        """Extract {variable} placeholders from the template."""
        import re
        return list(dict.fromkeys(re.findall(r"\{(\w+)\}", self.template)))

    def format(self, **kwargs: Any) -> str:
        """Fill template variables and return the formatted string.

        Args:
            **kwargs: Variable values (missing variables raise KeyError).

        Returns:
            Formatted prompt string.
        """
        # Check for missing variables
        missing = [v for v in self.input_variables if v not in kwargs]
        if missing:
            raise KeyError(f"Missing template variables: {missing}")

        return self.template.format(**{k: str(v) for k, v in kwargs.items()})

    def partial(self, **kwargs: Any) -> PromptTemplate:
        """Partially fill some variables, returning a new template.

        Args:
            **kwargs: Variables to pre-fill.

        Returns:
            New PromptTemplate with filled variables and remaining placeholders.
        """
        remaining = [v for v in self.input_variables if v not in kwargs]
        filled = self.template
        for k, v in kwargs.items():
            filled = filled.replace(f"{{{k}}}", str(v))
        return PromptTemplate(template=filled, input_variables=remaining)

    @classmethod
    def from_file(cls, path: str | Path, encoding: str = "utf-8") -> PromptTemplate:
        """Load a template from a text file.

        Args:
            path: Path to template file.
            encoding: File encoding.

        Returns:
            PromptTemplate with file content as template.

        Raises:
            FileNotFoundError: File does not exist.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Template file not found: {p}")
        text = p.read_text(encoding=encoding)
        return cls(template=text.strip())

    def __add__(self, other: PromptTemplate) -> PromptTemplate:
        """Concatenate two templates."""
        combined = self.template + "\n" + other.template
        vars = list(dict.fromkeys(self.input_variables + other.input_variables))
        return PromptTemplate(template=combined, input_variables=vars)

    def __str__(self) -> str:
        return self.template


class FewShotPromptTemplate(BaseModel):
    """Few-shot prompt template with examples.

    Combines prefix, example list, and suffix into a single prompt.

    Usage:
        tmpl = FewShotPromptTemplate(
            examples=[{"q": "2+2", "a": "4"}, {"q": "3+3", "a": "6"}],
            example_prompt=PromptTemplate("Q: {q}\\nA: {a}"),
            prefix="Math examples:",
            suffix="Q: {input}\\nA:",
        )
        result = tmpl.format(input="5+5")
    """

    examples: list[dict[str, Any]] = Field(default_factory=list, description="Few-shot examples")
    example_prompt: PromptTemplate = Field(description="Template for formatting each example")
    prefix: str = Field(default="", description="Text before examples")
    suffix: str = Field(default="", description="Text after examples with {input}")
    input_variables: list[str] = Field(default_factory=lambda: ["input"], description="Variables in suffix")
    example_separator: str = Field(default="\n\n", description="Separator between examples")

    model_config = {"arbitrary_types_allowed": True}

    def format(self, **kwargs: Any) -> str:
        """Format the full few-shot prompt.

        Args:
            **kwargs: Variables for the suffix template.

        Returns:
            Formatted prompt with examples.
        """
        parts = [self.prefix] if self.prefix else []
        for ex in self.examples:
            parts.append(self.example_prompt.format(**ex))
        suffix = self.suffix
        for k, v in kwargs.items():
            suffix = suffix.replace(f"{{{k}}}", str(v))
        parts.append(suffix)
        return self.example_separator.join(p for p in parts if p)

    def add_example(self, example: dict[str, Any]) -> FewShotPromptTemplate:
        """Add an example."""
        self.examples.append(example)
        return self
