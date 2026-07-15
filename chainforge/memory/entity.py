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
"""Entity Memory — extract and track entities with graph relationships.

Tracks entities (people, places, concepts) across conversations and
models relationships between them as a lightweight graph.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field


class Entity(BaseModel):
    """A tracked entity with attributes and relationships."""

    name: str = Field(description="Entity name")
    type: str = Field(default="unknown", description="Entity type (person, place, concept, etc.)")
    mentions: list[str] = Field(default_factory=list, description="Mention contexts")
    attributes: dict[str, list[str]] = Field(default_factory=dict, description="Extracted attributes")
    mention_count: int = Field(default=0, description="Times mentioned")


class Relation(BaseModel):
    """A directed relationship between two entities."""

    source: str = Field(description="Source entity name")
    target: str = Field(description="Target entity name")
    relation_type: str = Field(default="related_to", description="Type of relationship")
    strength: int = Field(default=1, description="Relationship strength / frequency")


class EntityMemory(BaseModel):
    """Extract and track entities from conversation history with graph relationships.

    Usage:
        memory = EntityMemory()
        memory.extract("Alice works at Google in Beijing.")
        # Alice -> works_at -> Google
        # Alice -> located_in -> Beijing

        # Get graph context
        neighbors = memory.get_neighbors("Alice")
        context = memory.get_context()
    """

    entities: dict[str, Entity] = Field(default_factory=dict)
    relations: list[Relation] = Field(default_factory=list, description="Entity relationship graph")
    max_entities: int = Field(default=100)

    # Pattern-based extraction
    _name_patterns: list[tuple[str, str]] = [
        (r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\s+(?:is|was|works|likes|has|said)", "person"),
        (r"(?:My name is|I am|I'm)\s+([A-Za-z]+)", "person"),
        (r"(?:in|at|near|from)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)", "location"),
    ]

    # Relationship extraction patterns: "X works at Y", "X lives in Y", etc.
    _relation_patterns: list[tuple[re.Pattern, str]] = [
        (re.compile(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\s+works?\s+(?:at|for)\s+([A-Z][a-zA-Z\s]+)'), "works_at"),
        (re.compile(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\s+lives?\s+in\s+([A-Z][a-zA-Z\s]+)'), "lives_in"),
        (re.compile(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\s+studies?\s+at\s+([A-Z][a-zA-Z\s]+)'), "studies_at"),
        (re.compile(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\s+is\s+(?:the\s+)?(founder|CEO|CTO|manager|lead|head)\s+of\s+([A-Z][a-zA-Z\s]+)'), "leads"),
    ]

    def extract(self, text: str, source: str = "user") -> dict[str, Entity]:
        """Extract entities and relationships from text.

        Args:
            text: Text to analyze.
            source: Source role ("user" or "assistant").

        Returns:
            Dict of extracted/newly updated entities by name.
        """
        updated = {}

        # Extract entities
        for pattern, etype in self._name_patterns:
            matches = re.findall(pattern, text)
            for name in matches:
                name_stripped = name.strip()
                if not name_stripped or len(name_stripped) < 2:
                    continue
                if name_stripped not in self.entities:
                    self.entities[name_stripped] = Entity(name=name_stripped, type=etype)

                entity = self.entities[name_stripped]
                entity.mention_count += 1
                context = text[:100] if len(text) > 100 else text
                if context not in entity.mentions:
                    entity.mentions.append(context)
                updated[name_stripped] = entity

        # Extract relationships
        for pattern, rel_type in self._relation_patterns:
            for match in pattern.finditer(text):
                source_name = match.group(1).strip()
                target_name = match.group(2).strip()
                if source_name in self.entities and target_name in self.entities:
                    self._add_relation(source_name, target_name, rel_type)
                elif source_name in self.entities:
                    # Auto-create target entity
                    if target_name not in self.entities:
                        self.entities[target_name] = Entity(name=target_name, type="unknown")
                    self._add_relation(source_name, target_name, rel_type)

        # Enforce entity limit
        if len(self.entities) > self.max_entities:
            sorted_ents = sorted(self.entities.values(), key=lambda e: e.mention_count, reverse=True)
            self.entities = {e.name: e for e in sorted_ents[:self.max_entities]}

        return updated

    def _add_relation(self, source: str, target: str, rel_type: str) -> None:
        """Add or strengthen a relationship."""
        for rel in self.relations:
            if rel.source == source and rel.target == target and rel.relation_type == rel_type:
                rel.strength += 1
                return
        self.relations.append(Relation(source=source, target=target, relation_type=rel_type))

    def get_entities(self, entity_type: str | None = None) -> dict[str, Entity]:
        """Get all entities, optionally filtered by type."""
        if entity_type:
            return {n: e for n, e in self.entities.items() if e.type == entity_type}
        return dict(self.entities)

    def get_neighbors(self, entity_name: str, max_depth: int = 1) -> list[dict[str, Any]]:
        """Get neighboring entities and relationship types.

        Args:
            entity_name: Entity to find neighbors for.
            max_depth: Graph traversal depth (1 = direct neighbors only).

        Returns:
            List of {"entity": str, "relation": str, "direction": "outgoing"|"incoming"}.
        """
        if entity_name not in self.entities:
            return []

        visited = {entity_name}
        neighbors: list[dict[str, Any]] = []

        def _traverse(current: str, depth: int) -> None:
            if depth > max_depth:
                return
            for rel in self.relations:
                if rel.source == current and rel.target not in visited:
                    visited.add(rel.target)
                    neighbors.append({
                        "entity": rel.target,
                        "relation": rel.relation_type,
                        "direction": "outgoing",
                        "strength": rel.strength,
                    })
                    _traverse(rel.target, depth + 1)
                elif rel.target == current and rel.source not in visited:
                    visited.add(rel.source)
                    neighbors.append({
                        "entity": rel.source,
                        "relation": rel.relation_type,
                        "direction": "incoming",
                        "strength": rel.strength,
                    })
                    _traverse(rel.source, depth + 1)

        _traverse(entity_name, 1)
        return neighbors

    def get_context(self) -> str:
        """Format entities and relationships as context string for the LLM."""
        if not self.entities:
            return ""
        parts = ["Known entities:"]

        # Top entities by mention count
        for name, ent in sorted(self.entities.items(), key=lambda x: x[1].mention_count, reverse=True)[:15]:
            line = f"- {name} ({ent.type}): mentioned {ent.mention_count} times"
            # Add relationship info
            rels = [r for r in self.relations if r.source == name or r.target == name]
            if rels:
                rel_strs = []
                for r in rels[:3]:
                    if r.source == name:
                        rel_strs.append(f"{r.relation_type} -> {r.target}")
                    else:
                        rel_strs.append(f"{r.source} -> {r.relation_type} -> {name}")
                if rel_strs:
                    line += f" [{', '.join(rel_strs)}]"
            parts.append(line)

        return "\n".join(parts)

    def clear(self) -> None:
        self.entities.clear()
        self.relations.clear()
