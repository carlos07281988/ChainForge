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
"""NL → Agent Compiler — compile natural language into executable agent workflows.

Usage:
    from chainforge.compiler import compile_workflow, list_templates

    # Template mode (no LLM needed)
    result = await compile_workflow("search web and answer")
    print(result.python_code)

    # List available templates
    print(list_templates())

    # Validate a schema
    from chainforge.compiler import validate_workflow
    errors = validate_workflow(schema)
"""

from chainforge.compiler.compiler import compile_workflow, compile_and_run, \
    validate_workflow, list_templates
from chainforge.compiler.schema import IntentSchema, CompilationResult, \
    NodeDef, EdgeDef, NodeType
from chainforge.compiler.parser import parse_nl, parse_nl_llm
from chainforge.compiler.templates import get_templates, find_matching_templates, \
    best_template, WorkflowTemplate
from chainforge.compiler.yamlgen import generate_yaml, generate_dict
from chainforge.compiler.validator import validate, format_errors, is_valid

__all__ = [
    "compile_workflow",
    "compile_and_run",
    "validate_workflow",
    "parse_nl",
    "parse_nl_llm",
    "list_templates",
    "get_templates",
    "find_matching_templates",
    "best_template",
    "WorkflowTemplate",
    "generate_yaml",
    "generate_dict",
    "validate",
    "format_errors",
    "is_valid",
    "IntentSchema",
    "CompilationResult",
    "NodeDef",
    "EdgeDef",
    "NodeType",
]
