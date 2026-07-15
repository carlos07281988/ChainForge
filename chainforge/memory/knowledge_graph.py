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
"""Knowledge Graph Memory — in-memory graph with entity-relation-store.

Stores entities and typed relationships as a directed property graph.
Supports semantic traversal, neighborhood queries, and context formatting.

Usage:
    kg = KnowledgeGraphMemory()
    kg.add_triple("Alice", "works_at", "Google")
    kg.add_triple("Alice", "likes", "Python")
    kg.add_entity_attr("Alice", "role", "engineer")

    ctx = kg.get_context("Alice")
    results = kg.query("Who works at Google?")
"""

from __future__ import annotations

import re
from typing import Any

from chainforge.logging import get_logger

logger = get_logger("memory.knowledge_graph")


class KnowledgeGraphMemory:
    """In-memory knowledge graph with entity, relation, and property storage.

    Supports:
    - Entity CRUD with attributes (key-value properties)
    - Typed directed relationships (subject -> predicate -> object)
    - Semantic context building for LLM prompts
    - Basic pattern matching for query
    """

    def __init__(self, max_entities: int = 500):
        self._entities: dict[str, dict[str, Any]] = {}  # name -> {attrs}
        self._relations: dict[str, list[tuple[str, str, dict]]] = {}  # subject -> [(predicate, object, props)]
        self._reverse_relations: dict[str, list[tuple[str, str, dict]]] = {}  # object -> [(subject, predicate, props)]
        self.max_entities = max_entities

    # ── Entity management ───────────────────────────────────────────────

    def add_entity(self, name: str, entity_type: str = "unknown", attrs: dict | None = None) -> None:
        """Add or update an entity."""
        if name not in self._entities:
            if len(self._entities) >= self.max_entities:
                return
            self._entities[name] = {"type": entity_type, "name": name}
        if attrs:
            self._entities[name].update(attrs)
        self._entities[name]["type"] = entity_type

    def add_entity_attr(self, name: str, key: str, value: Any) -> None:
        """Set an attribute on an entity."""
        if name not in self._entities:
            self.add_entity(name)
        self._entities[name][key] = value

    def get_entity(self, name: str) -> dict | None:
        return self._entities.get(name)

    def has_entity(self, name: str) -> bool:
        return name in self._entities

    def remove_entity(self, name: str) -> None:
        self._entities.pop(name, None)
        self._relations.pop(name, None)
        # Clean up reverse relations
        new_reverse: dict[str, list] = {}
        for obj, rels in self._reverse_relations.items():
            filtered = [(s, p, props) for s, p, props in rels if s != name and obj != name]
            if filtered:
                new_reverse[obj] = filtered
        self._reverse_relations = new_reverse

    # ── Relation management ─────────────────────────────────────────────

    def add_triple(self, subject: str, predicate: str, obj: str, props: dict | None = None) -> None:
        """Add a directed relation: subject -> predicate -> object."""
        self.add_entity(subject)
        self.add_entity(obj)

        if subject not in self._relations:
            self._relations[subject] = []
        self._relations[subject].append((predicate, obj, props or {}))

        if obj not in self._reverse_relations:
            self._reverse_relations[obj] = []
        self._reverse_relations[obj].append((subject, predicate, props or {}))

    def get_relations(self, subject: str) -> list[tuple[str, str, dict]]:
        """Get all outgoing relations from a subject."""
        return self._relations.get(subject, [])

    def get_reverse_relations(self, obj: str) -> list[tuple[str, str, dict]]:
        """Get all incoming relations to an object."""
        return self._reverse_relations.get(obj, [])

    def query_objects(self, subject: str, predicate: str) -> list[str]:
        """Find objects connected by predicate: subject -> predicate -> ?"""
        return [obj for p, obj, _ in self._relations.get(subject, []) if p == predicate]

    def query_subjects(self, predicate: str, obj: str) -> list[str]:
        """Find subjects connected by predicate: ? -> predicate -> object"""
        return [subj for subj, p, _ in self._reverse_relations.get(obj, []) if p == predicate]

    # ── Semantic query ──────────────────────────────────────────────────

    def query(self, text: str) -> list[dict[str, Any]]:
        """Simple pattern matching query over the graph."""
        results = []
        text_lower = text.lower()

        for name in self._entities:
            if name.lower() in text_lower:
                results.append({
                    "entity": name,
                    "type": self._entities[name].get("type", "unknown"),
                    "attrs": {k: v for k, v in self._entities[name].items() if k not in ("name", "type")},
                    "relations": [(p, o) for p, o, _ in self._relations.get(name, [])],
                    "incoming": [(s, p) for s, p, _ in self._reverse_relations.get(name, [])],
                })

        # Pattern matching for known patterns
        for m in re.finditer(r'who\s+(works\s+(?:at|for)|is|lives\sin|likes|knows)\s+(.+)', text_lower):
            rel = m.group(1).replace(" ", "_")
            target = m.group(2).strip().title()
            for subj, rels in self._relations.items():
                for p, obj, _ in rels:
                    if p == rel and target.lower() in obj.lower():
                        results.append({
                            "entity": subj,
                            "relation": rel,
                            "target": obj,
                            "type": self._entities.get(subj, {}).get("type", "unknown"),
                        })

        return results

    def get_neighborhood(self, entity: str, depth: int = 1) -> dict[str, Any]:
        """Get the subgraph around an entity up to depth hops."""
        if entity not in self._entities:
            return {"entity": entity, "found": False}

        visited = {entity}
        subgraph = {
            "entity": entity,
            "type": self._entities[entity].get("type", "unknown"),
            "attrs": {k: v for k, v in self._entities[entity].items() if k not in ("name", "type")},
            "relations": [],
        }

        def _traverse(current: str, current_depth: int):
            if current_depth > depth:
                return
            for p, obj, props in self._relations.get(current, []):
                rel_entry = {"predicate": p, "object": obj, "direction": "outgoing", "props": props}
                if rel_entry not in subgraph["relations"]:
                    subgraph["relations"].append(rel_entry)
                if obj not in visited:
                    visited.add(obj)
                    _traverse(obj, current_depth + 1)
            for subj, p, props in self._reverse_relations.get(current, []):
                rel_entry = {"predicate": p, "subject": subj, "direction": "incoming", "props": props}
                if rel_entry not in subgraph["relations"]:
                    subgraph["relations"].append(rel_entry)
                if subj not in visited:
                    visited.add(subj)
                    _traverse(subj, current_depth + 1)

        _traverse(entity, 1)
        return subgraph

    def get_context(self, query: str | None = None, max_entities: int = 20) -> str:
        """Format the graph as context for an LLM prompt.

        If query is provided, only include relevant entities.
        """
        if not self._entities:
            return ""

        if query:
            relevant = self.query(query)
            entity_names = {r["entity"] for r in relevant}
        else:
            entity_names = set(self._entities.keys())

        # Limit to top entities by relation count
        scored = sorted(
            entity_names,
            key=lambda n: len(self._relations.get(n, [])) + len(self._reverse_relations.get(n, [])),
            reverse=True,
        )[:max_entities]

        parts = ["Knowledge Graph:"]
        for name in scored:
            entity = self._entities.get(name, {})
            attrs_str = ", ".join(f"{k}={v}" for k, v in entity.items() if k not in ("name",))
            line = f"- {name}"
            if attrs_str:
                line += f" ({attrs_str})"
            parts.append(line)

            # Outgoing
            for p, obj, _ in self._relations.get(name, [])[:3]:
                parts.append(f"    {name} --[{p}]--> {obj}")
            # Incoming
            for subj, p, _ in self._reverse_relations.get(name, [])[:2]:
                parts.append(f"    {subj} --[{p}]--> {name}")

        return "\n".join(parts)

    @property
    def all_entities(self) -> dict:
        """Return all entities (public accessor for graph queries)."""
        return dict(self._entities)

    @property
    def relation_graph(self) -> tuple:
        """Return (relations, reverse_relations) tuple for graph traversal."""
        return (
            dict(self._relations),
            dict(self._reverse_relations),
        )

    def stats(self) -> dict[str, int]:
        return {
            "entities": len(self._entities),
            "relations": sum(len(v) for v in self._relations.values()),
        }

    def clear(self) -> None:
        self._entities.clear()
        self._relations.clear()
        self._reverse_relations.clear()
