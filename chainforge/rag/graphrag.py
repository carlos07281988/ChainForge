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
"""GraphRAG — community detection + summarization for knowledge graph retrieval.

Extends KnowledgeGraphMemory with Microsoft GraphRAG-style pipeline:
1. Community detection (graph connectivity-based clustering)
2. Community summarization (LLM generates summary per community)
3. GraphRAG query (retrieve entities -> find communities -> return summaries)

Usage:
    from chainforge.rag.graphrag import GraphRAGPipeline

    pipeline = GraphRAGPipeline(llm=llm, kg=knowledge_graph)
    await pipeline.build_communities()
    answer = await pipeline.query("What does the graph say about Alice?")
"""

from __future__ import annotations

from typing import Any

from chainforge.core.llm import LLM
from chainforge.core.message import Message
from chainforge.logging import get_logger
from chainforge.memory.knowledge_graph import KnowledgeGraphMemory

logger = get_logger("rag.graphrag")


class GraphRAGPipeline:
    """GraphRAG — community detection + summarization + query.

    Builds communities from a knowledge graph, generates summaries,
    and uses them for enhanced retrieval.

    Usage:
        kg = KnowledgeGraphMemory()
        kg.add_triple("Alice", "works_at", "Google")
        kg.add_triple("Bob", "works_at", "Google")
        kg.add_triple("Alice", "likes", "Python")

        pipeline = GraphRAGPipeline(llm=llm, kg=kg)
        await pipeline.build_communities()
        result = await pipeline.query("Who works with Alice?")
    """

    def __init__(
        self,
        llm: LLM,
        kg: KnowledgeGraphMemory | None = None,
        min_community_size: int = 2,
    ):
        self._llm = llm
        self._kg = kg or KnowledgeGraphMemory()
        self.min_community_size = min_community_size
        self._communities: list[dict[str, Any]] = []  # [{id, entities, summary}]

    @property
    def kg(self) -> KnowledgeGraphMemory:
        return self._kg

    def build_communities(self) -> list[dict[str, Any]]:
        """Detect communities in the knowledge graph using connectivity clustering.

        Uses simple BFS-based connected components clustering.
        For larger graphs, consider Leiden/Louvain algorithms.
        """
        entities = set(self._kg._entities.keys()) if hasattr(self._kg, "_entities") else set()
        if not entities:
            self._communities = []
            return self._communities

        # Build adjacency list
        adj: dict[str, set[str]] = {e: set() for e in entities}
        if hasattr(self._kg, "_relations"):
            for subject, rels in self._kg._relations.items():
                for _p, obj, _props in rels:
                    if subject in adj:
                        adj[subject].add(obj)
                    if obj in adj:
                        adj[obj].add(subject)
        if hasattr(self._kg, "_reverse_relations"):
            for obj, rev_rels in self._kg._reverse_relations.items():
                for subj, _p, _props in rev_rels:
                    if subj in adj:
                        adj[subj].add(obj)
                    if obj in adj:
                        adj[obj].add(subj)

        # BFS connected components
        visited: set[str] = set()
        communities: list[set[str]] = []

        for entity in entities:
            if entity in visited:
                continue
            # BFS
            component: set[str] = {entity}
            queue = [entity]
            while queue:
                current = queue.pop(0)
                for neighbor in adj.get(current, set()):
                    if neighbor not in visited and neighbor not in component:
                        component.add(neighbor)
                        visited.add(neighbor)
                        queue.append(neighbor)
            visited.add(entity)
            if len(component) >= self.min_community_size:
                communities.append(component)
            else:
                # Small components get merged into "other"
                pass

        # Store as community dicts
        self._communities = [
            {
                "id": f"community_{i}",
                "entities": sorted(comp),
                "summary": "",
            }
            for i, comp in enumerate(communities)
        ]

        logger.info(f"Built {len(self._communities)} communities from {len(entities)} entities")
        return self._communities

    async def summarize_communities(self) -> list[dict[str, Any]]:
        """Generate LLM summaries for each community.

        For each community, extracts the subgraph and asks the LLM
        to summarize what it represents.
        """
        if not self._communities:
            self.build_communities()

        for community in self._communities:
            # Build subgraph context
            subgraph_lines = []
            for entity in community["entities"]:
                if hasattr(self._kg, "_relations"):
                    for p, obj, _props in self._kg._relations.get(entity, []):
                        if obj in community["entities"]:
                            subgraph_lines.append(f"{entity} --[{p}]--> {obj}")
                if hasattr(self._kg, "_reverse_relations"):
                    for subj, p, _props in self._kg._reverse_relations.get(entity, []):
                        if subj in community["entities"]:
                            subgraph_lines.append(f"{subj} --[{p}]--> {entity}")

            if not subgraph_lines:
                community["summary"] = f"Entities: {', '.join(community['entities'][:10])}"
                continue

            subgraph_text = "\n".join(subgraph_lines[:30])

            try:
                resp = await self._llm.generate([
                    Message.system("Summarize what this group of entities represents in the knowledge graph."),
                    Message.user(f"Entities: {', '.join(community['entities'][:20])}\n\nRelations:\n{subgraph_text}"),
                ])
                community["summary"] = resp.content or ""
                logger.debug(f"Community '{community['id']}': {len(community['entities'])} entities, {len(community['summary'])} chars")
            except Exception as e:
                community["summary"] = f"Entities: {', '.join(community['entities'][:10])}"
                logger.warning(f"Summarization failed for community: {e}")

        return self._communities

    async def query(self, query: str, k: int = 3) -> str:
        """Query using GraphRAG: find entities -> get communities -> return summaries.

        Args:
            query: User query.
            k: Max communities to include.

        Returns:
            Context string with relevant community summaries and entity details.
        """
        if not self._communities:
            self.build_communities()

        # Find relevant communities by entity match
        query_lower = query.lower()
        scored_communities = []

        for community in self._communities:
            score = 0
            for entity in community["entities"]:
                if entity.lower() in query_lower:
                    score += 2
                # Check if entity appears in entity attributes
                if hasattr(self._kg, "_entities"):
                    ent_data = self._kg._entities.get(entity, {})
                    for val in ent_data.values():
                        if isinstance(val, str) and query_lower in val.lower():
                            score += 1

            if score > 0:
                scored_communities.append((score, community))

        scored_communities.sort(key=lambda x: x[0], reverse=True)
        top = scored_communities[:k]

        if not top:
            # Fall back to direct KG query
            return self._kg.get_context(query)

        # Build context with summaries
        parts = ["[GraphRAG Results]"]
        for score, community in top:
            summary = community.get("summary", "")
            entities = community["entities"][:10]
            entities_str = ", ".join(entities)
            if summary:
                parts.append(f"\nCommunity: {entities_str}\nSummary: {summary}")
            else:
                parts.append(f"\nRelated entities: {entities_str}")

        return "\n".join(parts)

    def stats(self) -> dict[str, Any]:
        """Return pipeline statistics."""
        return {
            "communities": len(self._communities),
            "total_entities": len(self._kg._entities) if hasattr(self._kg, "_entities") else 0,
            "avg_community_size": round(
                sum(len(c["entities"]) for c in self._communities) / len(self._communities), 1
            ) if self._communities else 0,
            "summarized": sum(1 for c in self._communities if c.get("summary")),
        }
