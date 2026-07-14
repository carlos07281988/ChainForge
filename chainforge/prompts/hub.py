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
"""Prompt Hub — registry for named prompt templates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from chainforge.logging import get_logger
from chainforge.prompts.template import PromptTemplate

logger = get_logger("prompts.hub")


class PromptHub:
    """Registry for named prompt templates with save/load/list.

    Usage:
        hub = PromptHub()
        hub.register("greeting", PromptTemplate("Hello, {name}!"))

        tmpl = hub.get("greeting")
        print(tmpl.format(name="Alice"))

        hub.save_to_dir("/path/to/templates")
        hub.load_from_dir("/path/to/templates")
    """

    def __init__(self):
        self._templates: dict[str, PromptTemplate] = {}

    def register(self, name: str, template: PromptTemplate, overwrite: bool = False) -> None:
        """Register a template by name.

        Args:
            name: Template name.
            template: PromptTemplate instance.
            overwrite: Overwrite existing (default False).

        Raises:
            KeyError: Template exists and overwrite is False.
        """
        if name in self._templates and not overwrite:
            raise KeyError(f"Template '{name}' already exists. Use overwrite=True.")
        self._templates[name] = template
        logger.info(f"Registered prompt template: {name}")

    def get(self, name: str) -> PromptTemplate | None:
        """Get a template by name."""
        return self._templates.get(name)

    def list(self) -> list[dict[str, Any]]:
        """List all registered templates."""
        return [
            {"name": name, "variables": tmpl.input_variables, "preview": tmpl.template[:80]}
            for name, tmpl in self._templates.items()
        ]

    def remove(self, name: str) -> bool:
        """Remove a template.

        Returns:
            True if removed, False if not found.
        """
        return self._templates.pop(name, None) is not None

    def save_to_dir(self, directory: str | Path) -> None:
        """Save all templates as .txt files to a directory."""
        Path(directory).mkdir(parents=True, exist_ok=True)
        for name, tmpl in self._templates.items():
            path = Path(directory) / f"{name}.txt"
            path.write_text(tmpl.template)
        logger.info(f"Saved {len(self._templates)} templates to {directory}")

    def load_from_dir(self, directory: str | Path) -> int:
        """Load templates from .txt files in a directory.

        Returns:
            Number of templates loaded.
        """
        count = 0
        for f in Path(directory).glob("*.txt"):
            name = f.stem
            template = PromptTemplate.from_file(f)
            self._templates[name] = template
            count += 1
        logger.info(f"Loaded {count} templates from {directory}")
        return count

    @property
    def count(self) -> int:
        return len(self._templates)
