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
"""Compiler schema — the intermediate representation (IR) of agent workflows.

IntentSchema is the structured output of the NL parser and the input to codegen.
It represents an agent workflow as a directed graph of typed nodes with edges.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    """Types of nodes in an agent workflow graph."""
    entry = "entry"
    exit = "exit"
    llm = "llm"
    tool = "tool"
    conditional = "conditional"
    agent = "agent"
    step = "step"
    merge = "merge"


class EdgeDef(BaseModel):
    """A directed edge between two nodes, optionally with a condition label."""

    source: str = Field(description="Source node ID")
    target: str = Field(description="Target node ID")
    condition: str | None = Field(default=None, description="Condition label for routing")


class NodeDef(BaseModel):
    """A single node in the agent workflow graph."""

    id: str = Field(description="Unique node identifier")
    type: NodeType = Field(description="Node type")
    description: str = Field(default="", description="Human-readable description")
    tool: str | None = Field(default=None, description="Tool name (for tool nodes)")
    prompt: str | None = Field(default=None, description="LLM prompt (for llm nodes)")
    agent_id: str | None = Field(default=None, description="Agent ID (for agent nodes)")
    config: dict[str, Any] = Field(default_factory=dict, description="Additional configuration")


class IntentSchema(BaseModel):
    """Intermediate representation of an agent workflow.

    Produced by the NL parser, consumed by codegen.
    Represents a directed graph of agent execution steps.
    """

    name: str = Field(default="agent_workflow", description="Workflow name")
    description: str = Field(default="", description="What this workflow does")
    nodes: list[NodeDef] = Field(description="All nodes in the workflow")
    edges: list[EdgeDef] = Field(description="All edges connecting nodes")
    tools: list[str] = Field(default_factory=list, description="Tools referenced by this workflow")
    config: dict[str, Any] = Field(default_factory=dict, description="Global workflow configuration")

    def node_ids(self) -> set[str]:
        return {n.id for n in self.nodes}

    def get_node(self, node_id: str) -> NodeDef | None:
        for n in self.nodes:
            if n.id == node_id:
                return n
        return None

    def get_outgoing(self, node_id: str) -> list[EdgeDef]:
        return [e for e in self.edges if e.source == node_id]

    def get_incoming(self, node_id: str) -> list[EdgeDef]:
        return [e for e in self.edges if e.target == node_id]

    def get_entry_nodes(self) -> list[NodeDef]:
        all_targets = {e.target for e in self.edges}
        return [n for n in self.nodes if n.id not in all_targets]

    def get_exit_nodes(self) -> list[NodeDef]:
        all_sources = {e.source for e in self.edges}
        return [n for n in self.nodes if n.id not in all_sources
                and n.type != NodeType.exit]

    def get_conditionals(self) -> list[NodeDef]:
        return [n for n in self.nodes if n.type == NodeType.conditional]

    def get_tool_names(self) -> list[str]:
        return list({n.tool for n in self.nodes if n.tool})

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IntentSchema":
        return cls(**data)

    def __repr__(self) -> str:
        return (f"IntentSchema(name={self.name!r}, nodes={len(self.nodes)}, "
                f"edges={len(self.edges)})")


# ── CompilationResult ─────────────────────────────────────────────────────


class CompilationResult(BaseModel):
    """The result of compiling an IntentSchema into executable output."""

    intent_schema: IntentSchema = Field(description="The intent schema", alias="schema")
    model_config = {"populate_by_name": True}
    python_code: str = Field(default="", description="Generated Python code")
    yaml_output: str = Field(default="", description="Generated YAML output")
    errors: list[str] = Field(default_factory=list, description="Validation errors")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")
    success: bool = Field(default=True, description="Whether compilation succeeded")

    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def summary(self) -> str:
        schema = self.intent_schema
        parts = [f"Compilation: {'✅' if self.success else '❌'}"]
        parts.append(f"  Nodes: {len(schema.nodes)}")
        parts.append(f"  Edges: {len(schema.edges)}")
        parts.append(f"  Tools: {schema.get_tool_names()}")
        if self.errors:
            parts.append(f"  Errors: {len(self.errors)}")
            for e in self.errors[:3]:
                parts.append(f"    - {e}")
        if self.warnings:
            parts.append(f"  Warnings: {len(self.warnings)}")
            for w in self.warnings[:3]:
                parts.append(f"    - {w}")
        return "\n".join(parts)
