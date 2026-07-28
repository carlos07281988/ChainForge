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
"""GraphRAG 3.0 data models — Node, Edge, Graph, SubGraph."""

from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Node(BaseModel):
    """A node in the knowledge graph."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    type: str = ""  # Customer, Order, Product, Tool, Agent, etc.
    label: str = ""  # Human-readable label
    properties: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] | None = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class Edge(BaseModel):
    """An edge (relationship) in the knowledge graph."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    source_id: str = ""
    target_id: str = ""
    type: str = ""  # PURCHASED, OWNS, REFUNDED, CALLS, etc.
    label: str = ""
    properties: dict[str, Any] = Field(default_factory=dict)
    weight: float = 1.0
    created_at: float = Field(default_factory=time.time)


class Graph(BaseModel):
    """An in-memory knowledge graph."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    nodes: dict[str, Node] = Field(default_factory=dict)
    edges: list[Edge] = Field(default_factory=list)

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)


class SubGraph(BaseModel):
    """A subgraph extracted from a query result."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    query: str = ""
    score: float = 0.0

    def to_json(self) -> dict:
        return self.model_dump()
