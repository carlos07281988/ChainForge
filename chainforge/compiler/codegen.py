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
"""Codegen — IntentSchema → executable CyclicGraph Python code."""

from __future__ import annotations

from chainforge.compiler.schema import IntentSchema, NodeDef, NodeType
from chainforge.compiler.validator import validate


def generate_python(schema: IntentSchema, indent: str = "    ") -> str:
    """Generate executable Python code for a CyclicGraph from an IntentSchema.

    Args:
        schema: The IntentSchema to compile.
        indent: Indentation string (default 4 spaces).

    Returns:
        Python source code that creates and runs a CyclicGraph.
    """
    errors, warnings = validate(schema)
    if errors:
        error_msg = "\n".join(f"# ERROR: {e}" for e in errors)
        return f"# Compilation failed with {len(errors)} error(s):\n{error_msg}"

    lines: list[str] = []
    lines.append('"""Auto-generated agent workflow: {0}"""'.format(schema.name))
    lines.append("")
    lines.append("import asyncio")
    lines.append("from chainforge.core.graph import CyclicGraph, GraphNodeType")
    lines.append("from chainforge.core.stream import EventType")
    lines.append("")

    # Tool imports
    tool_names = schema.get_tool_names()
    if tool_names:
        tools_str = ", ".join(tool_names)
        lines.append(f"# Tools needed: {tools_str}")
        lines.append(f"from chainforge.tools import {tools_str}")
        lines.append("")

    # Build graph
    lines.append("def build_graph() -> CyclicGraph:")
    lines.append(f"{indent}\"\"\"Build the {schema.name} workflow graph.\"\"\"")
    lines.append(f"{indent}graph = CyclicGraph(name={schema.name!r})")
    lines.append("")

    # Add nodes
    for node in schema.nodes:
        add_method = _node_to_add_method(node, indent)
        lines.append(add_method)

    lines.append("")

    # Add edges
    for edge in schema.edges:
        edge_line = f'{indent}graph.add_edge({edge.source!r}, {edge.target!r}'
        if edge.condition:
            edge_line += f', condition={edge.condition!r}'
        edge_line += ')'
        lines.append(edge_line)

    lines.append("")
    lines.append(f"{indent}return graph")
    lines.append("")

    # Main execution
    lines.append("")
    lines.append("async def main():")
    lines.append(f"{indent}graph = build_graph()")
    lines.append(f'{indent}stream = graph.run("Your input here")')
    lines.append(f"{indent}async for event in stream:")
    lines.append(f"{indent}{indent}if event.type == EventType.text and event.content:")
    lines.append(f"{indent}{indent}{indent}print(event.content, end='', flush=True)")
    lines.append(f"{indent}{indent}elif event.type == EventType.error:")
    lines.append(f"{indent}{indent}{indent}print(f'[Error] {{event.content}}')")
    lines.append("")
    lines.append("if __name__ == '__main__':")
    lines.append(f"{indent}asyncio.run(main())")
    lines.append("")

    return "\n".join(lines)


def _node_to_add_method(node: NodeDef, indent: str) -> str:
    """Generate the add_* method call for a node."""
    type_map = {
        NodeType.entry: "add_entry",
        NodeType.exit: "add_exit",
        NodeType.llm: "add_llm",
        NodeType.tool: "add_tool_node",
        NodeType.agent: "add_agent_node",
    }

    node_id = node.id
    desc = node.description or node_id

    if node.type in type_map:
        method = type_map[node.type]
        params = f"{node_id!r}"

        if node.type == NodeType.entry:
            return f'{indent}graph.{method}({params}, description={desc!r})'

        elif node.type == NodeType.exit:
            return f'{indent}graph.{method}({params}, description={desc!r})'

        elif node.type == NodeType.llm:
            fn_call = _generate_llm_fn(node)
            return f'{indent}graph.{method}({params}, fn={fn_call}, description={desc!r})'

        elif node.type == NodeType.tool:
            if node.tool:
                return (
                    f'{indent}graph.{method}({params}, '
                    f'tool_fn={node.tool}, description={desc!r})'
                )
            return (
                f'{indent}graph.{method}({params}, description={desc!r})'
            )

        elif node.type == NodeType.agent:
            return f'{indent}graph.{method}({params}, description={desc!r})'

    # Generic node
    return f'{indent}graph.add_node({node_id!r}, node_type=GraphNodeType.{node.type.value}, description={desc!r})'


def _generate_llm_fn(node: NodeDef) -> str:
    """Generate an inline async function for an LLM node."""
    prompt = node.prompt or "Process the input"
    return f'lambda msgs: f"LLM: {prompt}"'


def generate_yaml_schema(schema: IntentSchema) -> str:
    """Generate a YAML description of the workflow (rendered as Python comment)."""
    lines = [f"# Workflow: {schema.name}", f"# Description: {schema.description}"]
    lines.append("# Nodes:")
    for n in schema.nodes:
        lines.append(f"  #   - {n.id} ({n.type.value})")
    lines.append("# Edges:")
    for e in schema.edges:
        cond = f" [{e.condition}]" if e.condition else ""
        lines.append(f"  #   {e.source} → {e.target}{cond}")
    lines.append("# Tools:")
    for t in schema.get_tool_names():
        lines.append(f"  #   - {t}")
    return "\n".join(lines)
