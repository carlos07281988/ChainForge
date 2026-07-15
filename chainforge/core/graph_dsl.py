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
"""Declarative Workflow DSL — define CyclicGraph workflows as YAML/JSON."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from chainforge.core.graph import CyclicGraph, GraphNodeType


class WorkflowNodeDef(BaseModel):
    """A node definition in a workflow."""
    id: str = Field(description="Unique node identifier")
    type: str = Field(default="step", description="Node type: tool, llm, agent, exit, entry, step")
    fn: str | None = Field(default=None, description="Function name or callable path")
    description: str = Field(default="")

class WorkflowEdgeDef(BaseModel):
    """An edge definition in a workflow."""
    source: str = Field(description="Source node ID")
    target: str = Field(description="Target node ID")
    condition: str | None = Field(default=None, description="Condition label for routing")

class WorkflowDef(BaseModel):
    """A complete workflow definition."""
    name: str = Field(default="workflow")
    nodes: list[WorkflowNodeDef] = Field(default_factory=list)
    edges: list[WorkflowEdgeDef] = Field(default_factory=list)
    max_iterations: int = Field(default=50)
    max_cycle_depth: int = Field(default=10)


TYPE_MAP = {
    "entry": GraphNodeType.entry,
    "exit": GraphNodeType.exit,
    "tool": GraphNodeType.tool,
    "llm": GraphNodeType.llm,
    "agent": GraphNodeType.agent,
    "step": GraphNodeType.step,
    "router": GraphNodeType.router,
    "conditional": GraphNodeType.conditional,
    "merge": GraphNodeType.merge,
}

TYPE_REVERSE = {v: k for k, v in TYPE_MAP.items()}

def parse_workflow_dict(data: dict) -> CyclicGraph:
    """Parse a workflow definition dict into a CyclicGraph."""
    wf = WorkflowDef.model_validate(data)
    graph = CyclicGraph(
        name=wf.name,
        max_iterations=wf.max_iterations,
        max_cycle_depth=wf.max_cycle_depth,
    )
    for ndef in wf.nodes:
        node_type = TYPE_MAP.get(ndef.type, GraphNodeType.step)
        graph.add_node(ndef.id, node_type=node_type, description=ndef.description)
    for edef in wf.edges:
        if edef.condition:
            graph.add_edge(edef.source, edef.target, condition=edef.condition)
        else:
            graph.add_edge(edef.source, edef.target)
    return graph

def parse_workflow_json(json_str: str) -> CyclicGraph:
    """Parse a JSON workflow definition into a CyclicGraph."""
    data = json.loads(json_str)
    return parse_workflow_dict(data)

def parse_workflow_yaml(yaml_str: str) -> CyclicGraph:
    """Parse a YAML workflow definition into a CyclicGraph.
    Requires PyYAML. Falls back to JSON if YAML fails.
    """
    try:
        import yaml as _yaml
        data = _yaml.safe_load(yaml_str)
        return parse_workflow_dict(data)
    except ImportError:
        try:
            return parse_workflow_json(yaml_str)
        except json.JSONDecodeError:
            raise ImportError("PyYAML required. Install: pip install pyyaml")

def workflow_to_dict(graph: CyclicGraph) -> dict:
    """Serialize a CyclicGraph to a dict for YAML/JSON export."""
    nodes = []
    for nid, node in graph.nodes.items():
        nodes.append({
            "id": nid,
            "type": TYPE_REVERSE.get(node.type, node.type.value),
            "description": node.description,
        })
    edges = []
    for edge in graph.edges:
        edef = {"source": edge.source, "target": edge.target}
        if edge.condition:
            edef["condition"] = edge.condition
        edges.append(edef)
    return {
        "name": graph.name,
        "nodes": nodes,
        "edges": edges,
        "max_iterations": graph.max_iterations,
        "max_cycle_depth": graph.max_cycle_depth,
    }

__all__ = [
    "parse_workflow_dict", "parse_workflow_json", "parse_workflow_yaml",
    "workflow_to_dict", "WorkflowDef", "WorkflowNodeDef", "WorkflowEdgeDef",
]
