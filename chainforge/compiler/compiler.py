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
"""Compiler — unified interface for the NL → Agent workflow compiler.

Usage:
    from chainforge.compiler import compile_workflow

    # Template mode (no LLM needed)
    result = await compile_workflow("search web and answer")

    # LLM mode (requires a provider)
    from chainforge.providers import OpenAIProvider
    llm = OpenAIProvider(model="gpt-4o")
    result = await compile_workflow("search web for news, then summarize", llm=llm)

    # Output formats
    print(result.python_code)
    print(result.yaml_output)
    print(result.summary())

    # List available templates
    from chainforge.compiler import list_templates
    for t in list_templates():
        print(f"{t['name']}: {t['description']}")
"""

from __future__ import annotations

from typing import Any

from chainforge.compiler.codegen import generate_python, generate_yaml_schema
from chainforge.compiler.parser import parse
from chainforge.compiler.schema import CompilationResult, IntentSchema
from chainforge.compiler.templates import list_templates
from chainforge.compiler.validator import format_errors, validate
from chainforge.compiler.yamlgen import generate_dict, generate_yaml
from chainforge.logging import get_logger

logger = get_logger("compiler")


async def compile_workflow(text: str, llm: Any | None = None,
                            output_format: str = "python",
                            **options: Any) -> CompilationResult:
    """Compile natural language into an executable agent workflow.

    This is the main entry point for the NL → Agent Compiler.

    Args:
        text: Natural language description of the workflow.
        llm: Optional LLM provider for LLM mode parsing.
        output_format: Output format — "python", "yaml", or "both".
        **options: Additional options passed to codegen.

    Returns:
        CompilationResult with generated code and validation info.
    """
    logger.info(f"Compiling: {text[:100]}")

    # Step 1: Parse NL → IntentSchema
    schema = await parse(text, llm)
    if schema is None:
        return CompilationResult(
            schema=IntentSchema(name="error", nodes=[], edges=[]),
            success=False,
            errors=[f"Could not parse: '{text[:100]}'. "
                    f"No template matched and no LLM provided."],
        )

    # Step 2: Validate
    errors, warnings = validate(schema)

    # Step 3: Generate code
    python_code = generate_python(schema) if not errors else ""
    yaml_output = generate_yaml(schema) if not errors else ""

    return CompilationResult(
        schema=schema,
        python_code=python_code,
        yaml_output=yaml_output,
        errors=errors,
        warnings=warnings,
        success=len(errors) == 0,
    )


async def compile_and_run(text: str, llm: Any | None = None,
                           **options: Any) -> None:
    """Compile and immediately execute the generated workflow.

    Args:
        text: Natural language description of the workflow.
        llm: Optional LLM provider for LLM mode.
        **options: Additional options.
    """
    from chainforge.core.graph import CyclicGraph

    result = await compile_workflow(text, llm, **options)
    print(result.summary())

    if not result.success:
        return

    # Build and run the CyclicGraph from the schema
    graph = _schema_to_graph(result.schema)
    stream = graph.run("Execute workflow")
    from chainforge.core.stream import EventType
    async for event in stream:
        if event.type == EventType.text and event.content:
            print(event.content, end="", flush=True)
        elif event.type == EventType.error:
            print(f"\n[Error] {event.content}")


def _schema_to_graph(schema: IntentSchema):
    """Convert an IntentSchema to a live CyclicGraph instance.

    This creates a graph with placeholder functions for LLM/tool nodes.
    For full execution, use the generated Python code instead.
    """
    from chainforge.core.graph import CyclicGraph, GraphNodeType

    graph = CyclicGraph(name=schema.name)

    type_methods = {
        "entry": "add_entry",
        "exit": "add_exit",
        "llm": "add_llm",
        "tool": "add_tool_node",
        "agent": "add_agent_node",
    }

    for node in schema.nodes:
        method = type_methods.get(node.type.value) or "add_node"
        if hasattr(graph, method):
            getattr(graph, method)(node.id, description=node.description)
        else:
            graph.add_node(node.id, description=node.description)

    for edge in schema.edges:
        graph.add_edge(edge.source, edge.target, condition=edge.condition)

    return graph


def validate_workflow(schema: IntentSchema) -> str:
    """Validate a workflow and return a human-readable report."""
    return format_errors(schema)


# Re-export for convenience
__all__ = [
    "compile_workflow",
    "compile_and_run",
    "validate_workflow",
    "list_templates",
]
