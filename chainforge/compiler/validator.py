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
"""Validator — validate IntentSchema for correctness.

Checks:
  - All node references in edges exist
  - At least one entry and one exit node
  - No duplicate node IDs
  - Conditional nodes have conditions on outgoing edges
  - Tool nodes have tool names
  - Graph is connected (no orphan nodes)
"""

from __future__ import annotations

from chainforge.compiler.schema import IntentSchema, NodeType


def validate(schema: IntentSchema) -> tuple[list[str], list[str]]:
    """Validate an IntentSchema.

    Args:
        schema: The IntentSchema to validate.

    Returns:
        (errors, warnings) — lists of error and warning messages.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Check node IDs are unique
    node_ids = [n.id for n in schema.nodes]
    if len(node_ids) != len(set(node_ids)):
        seen = set()
        for nid in node_ids:
            if nid in seen:
                errors.append(f"Duplicate node ID: '{nid}'")
            seen.add(nid)

    # 2. Check at least one entry and one exit
    entries = [n for n in schema.nodes if n.type == NodeType.entry]
    if len(entries) == 0:
        errors.append("No entry node found (need at least one)")
    elif len(entries) > 1:
        warnings.append(f"Multiple entry nodes ({len(entries)}), using first")

    exits = [n for n in schema.nodes if n.type == NodeType.exit]
    if len(exits) == 0:
        errors.append("No exit node found (need at least one)")

    # 3. Check all edge references are valid
    valid_ids = set(node_ids)
    for edge in schema.edges:
        if edge.source not in valid_ids:
            errors.append(f"Edge references unknown source node: '{edge.source}'")
        if edge.target not in valid_ids:
            errors.append(f"Edge references unknown target node: '{edge.target}'")

    # 4. Check conditional nodes
    conditional_ids = {n.id for n in schema.nodes if n.type == NodeType.conditional}
    for cn in conditional_ids:
        outgoing = schema.get_outgoing(cn)
        if not outgoing:
            errors.append(f"Conditional node '{cn}' has no outgoing edges")
        else:
            no_condition = [e for e in outgoing if not e.condition]
            if no_condition:
                errors.append(
                    f"Conditional node '{cn}' has edge(s) without condition: "
                    f"{[e.target for e in no_condition]}"
                )

    # 5. Check tool nodes have tool names
    for node in schema.nodes:
        if node.type == NodeType.tool and not node.tool:
            errors.append(f"Tool node '{node.id}' has no tool name")

    # 6. Check LLM nodes have prompts (warning, not error — default prompts exist)
    for node in schema.nodes:
        if node.type == NodeType.llm and not node.prompt:
            warnings.append(f"LLM node '{node.id}' has no prompt")

    # 7. Check for orphan nodes (no incoming edges, not entry)
    for node in schema.nodes:
        if node.type != NodeType.entry:
            incoming = schema.get_incoming(node.id)
            if not incoming:
                warnings.append(f"Node '{node.id}' has no incoming edges (orphan)")

    # 8. Check all nodes are reachable from entry
    if entries:
        entry_id = entries[0].id
        reachable = _reachable_nodes(schema, entry_id)
        unreachable = [n.id for n in schema.nodes if n.id not in reachable]
        if unreachable:
            warnings.append(f"Nodes unreachable from entry: {unreachable}")

    return errors, warnings


def _reachable_nodes(schema: IntentSchema, start_id: str) -> set[str]:
    """BFS from start_id to find all reachable nodes."""
    visited: set[str] = set()
    queue = [start_id]
    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        outgoing = schema.get_outgoing(current)
        for edge in outgoing:
            if edge.target not in visited:
                queue.append(edge.target)
    return visited


def is_valid(schema: IntentSchema) -> bool:
    """Quick check: returns True if there are no errors."""
    errors, _ = validate(schema)
    return len(errors) == 0


def format_errors(schema: IntentSchema) -> str:
    """Return a human-readable validation report."""
    errors, warnings = validate(schema)
    parts: list[str] = []
    if not errors and not warnings:
        return "✅ Schema is valid"
    if errors:
        parts.append(f"❌ {len(errors)} error(s):")
        for e in errors:
            parts.append(f"  - {e}")
    if warnings:
        parts.append(f"⚠️  {len(warnings)} warning(s):")
        for w in warnings:
            parts.append(f"  - {w}")
    return "\n".join(parts)
