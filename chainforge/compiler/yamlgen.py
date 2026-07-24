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
"""YAML codegen — IntentSchema → YAML workflow definition.

The YAML output is compatible with the existing Workflow DSL parser
(parse_workflow_dict / parse_workflow_yaml in chainforge.core.graph_dsl).
"""

from __future__ import annotations

import json
from typing import Any

from chainforge.compiler.schema import EdgeDef, IntentSchema, NodeDef, NodeType
from chainforge.compiler.validator import validate


def generate_yaml(schema: IntentSchema) -> str:
    """Generate a YAML workflow definition from an IntentSchema.

    The output is compatible with parse_workflow_yaml().

    Args:
        schema: The IntentSchema to convert.

    Returns:
        YAML string representing the workflow.
    """
    errors, _ = validate(schema)
    if errors:
        error_comment = "\n".join(f"# ERROR: {e}" for e in errors)
        return f"# Compilation failed with {len(errors)} error(s):\n{error_comment}"

    lines: list[str] = []
    lines.append(f"# Auto-generated workflow: {schema.name}")
    lines.append(f"# {schema.description}")
    lines.append("")
    lines.append(f"name: {schema.name}")
    lines.append(f"description: {schema.description or ''}")
    lines.append("")

    # Nodes
    lines.append("nodes:")
    for node in schema.nodes:
        lines.append(f"  - id: {node.id}")
        lines.append(f"    type: {node.type.value}")
        if node.description:
            lines.append(f"    description: \"{node.description}\"")
        if node.tool:
            lines.append(f"    tool: {node.tool}")
        if node.prompt:
            lines.append(f"    prompt: \"{_escape_yaml(node.prompt)}\"")
        if node.agent_id:
            lines.append(f"    agent_id: {node.agent_id}")
        if node.config:
            lines.append(f"    config: {_to_yaml_value(node.config)}")

    lines.append("")

    # Edges
    if schema.edges:
        lines.append("edges:")
        for edge in schema.edges:
            lines.append(f"  - source: {edge.source}")
            lines.append(f"    target: {edge.target}")
            if edge.condition:
                lines.append(f"    condition: {edge.condition}")

    lines.append("")

    # Tools (optional)
    if schema.tools:
        lines.append("tools:")
        for t in schema.tools:
            lines.append(f"  - {t}")

    return "\n".join(lines)


def generate_dict(schema: IntentSchema) -> dict[str, Any]:
    """Generate a dict representation (compatible with parse_workflow_dict).

    Args:
        schema: The IntentSchema to convert.

    Returns:
        Dict suitable for parse_workflow_dict().
    """
    type_map = {
        NodeType.entry: "entry",
        NodeType.exit: "exit",
        NodeType.llm: "llm",
        NodeType.tool: "tool",
        NodeType.conditional: "conditional",
        NodeType.agent: "agent",
        NodeType.step: "step",
        NodeType.merge: "merge",
    }

    nodes = []
    for n in schema.nodes:
        node_dict = {
            "id": n.id,
            "type": type_map.get(n.type, "step"),
            "description": n.description,
        }
        if n.tool:
            node_dict["tool"] = n.tool
        if n.prompt:
            node_dict["prompt"] = n.prompt
        if n.config:
            node_dict["config"] = n.config
        nodes.append(node_dict)

    edges = []
    for e in schema.edges:
        edge = {"source": e.source, "target": e.target}
        if e.condition:
            edge["condition"] = e.condition
        edges.append(edge)

    result: dict[str, Any] = {
        "name": schema.name,
        "description": schema.description,
        "nodes": nodes,
        "edges": edges,
    }
    if schema.tools:
        result["tools"] = schema.tools
    if schema.config:
        result["config"] = schema.config

    return result


def _escape_yaml(s: str) -> str:
    """Escape a string for YAML double-quoted format."""
    return s.replace('"', '\\"').replace("\n", "\\n")


def _to_yaml_value(obj: Any, indent: int = 4) -> str:
    """Convert a simple object to inline YAML value."""
    prefix = " " * indent
    if isinstance(obj, dict):
        items = []
        for k, v in obj.items():
            items.append(f"\n{prefix}{k}: {_to_yaml_value(v, indent + 2)}")
        return "{" + ",".join(items) + " }"
    if isinstance(obj, list):
        return "[" + ", ".join(str(v) for v in obj) + "]"
    if isinstance(obj, bool):
        return "true" if obj else "false"
    if isinstance(obj, str):
        return f"\"{_escape_yaml(obj)}\""
    return str(obj)
