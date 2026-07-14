# Copyright 2024 ChainForge Contributors
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
"""Entity Memory — extract and track entities across conversations."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field


class Entity(BaseModel):
    """A tracked entity with attributes."""
    name: str = Field(description="Entity name")
    type: str = Field(default="unknown", description="Entity type (person, place, etc.)")
    mentions: list[str] = Field(default_factory=list, description="Mention contexts")
    attributes: dict[str, list[str]] = Field(default_factory=dict, description="Extracted attributes")
    mention_count: int = Field(default=0, description="Times mentioned")


class EntityMemory(BaseModel):
    """Extract and track entities from conversation history.

    Usage:
        memory = EntityMemory()
        memory.extract("Alice lives in Beijing and works at Google.")
        entities = memory.get_entities()
        print(entities["Alice"])
    """

    entities: dict[str, Entity] = Field(default_factory=dict)
    max_entities: int = Field(default=100)

    # Simple pattern-based extraction
    _name_patterns: list = [
        (r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\s+(?:is|was|works|likes|has|said)", "person"),
        (r"(?:My name is|I am|I'm)\s+([A-Za-z]+)", "person"),
        (r"(?:in|at|near|from)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)", "location"),
    ]

    def extract(self, text: str, source: str = "user") -> dict[str, Entity]:
        """Extract entities from text.

        Args:
            text: Text to analyze.
            source: Source role ("user" or "assistant").

        Returns:
            Dict of extracted/newly updated entities by name.
        """
        updated = {}

        for pattern, etype in self._name_patterns:
            matches = re.findall(pattern, text)
            for name in matches:
                name = name.strip()
                if not name or len(name) < 2:
                    continue
                if name not in self.entities:
                    self.entities[name] = Entity(name=name, type=etype)

                entity = self.entities[name]
                entity.mention_count += 1
                # Store the context snippet
                context = text[:100] if len(text) > 100 else text
                if context not in entity.mentions:
                    entity.mentions.append(context)
                updated[name] = entity

        # Enforce limit
        if len(self.entities) > self.max_entities:
            sorted_ents = sorted(self.entities.values(), key=lambda e: e.mention_count, reverse=True)
            self.entities = {e.name: e for e in sorted_ents[:self.max_entities]}

        return updated

    def get_entities(self, entity_type: str | None = None) -> dict[str, Entity]:
        """Get all entities, optionally filtered by type."""
        if entity_type:
            return {n: e for n, e in self.entities.items() if e.type == entity_type}
        return dict(self.entities)

    def get_context(self) -> str:
        """Format entities as context string for the LLM."""
        if not self.entities:
            return ""
        parts = []
        for name, ent in sorted(self.entities.items(), key=lambda x: x[1].mention_count, reverse=True)[:20]:
            parts.append(f"- {name} ({ent.type}): mentioned {ent.mention_count} times")
        return "Known entities:\n" + "\n".join(parts)

    def clear(self) -> None:
        self.entities.clear()
