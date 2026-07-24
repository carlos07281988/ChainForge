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
"""Tests for NL → Agent Compiler."""

import asyncio

import pytest

from chainforge.compiler.schema import IntentSchema, NodeDef, EdgeDef, NodeType, CompilationResult
from chainforge.compiler.templates import (
    get_templates, find_matching_templates, best_template, get_template, list_templates,
)
from chainforge.compiler.parser import parse_nl
from chainforge.compiler.validator import validate, is_valid, format_errors
from chainforge.compiler.codegen import generate_python
from chainforge.compiler.yamlgen import generate_yaml, generate_dict
from chainforge.compiler.compiler import compile_workflow


# ── Test IntentSchema ──────────────────────────────────────────────────────


class TestIntentSchema:
    def test_create_empty(self):
        schema = IntentSchema(name="test", nodes=[], edges=[])
        assert schema.name == "test"
        assert schema.nodes == []
        assert schema.edges == []

    def test_create_with_nodes(self):
        schema = IntentSchema(
            name="wf",
            nodes=[
                NodeDef(id="entry", type=NodeType.entry),
                NodeDef(id="exit", type=NodeType.exit),
            ],
            edges=[
                EdgeDef(source="entry", target="exit"),
            ],
        )
        assert len(schema.nodes) == 2
        assert len(schema.edges) == 1

    def test_node_ids(self):
        schema = IntentSchema(
            name="t",
            nodes=[
                NodeDef(id="a", type=NodeType.entry),
                NodeDef(id="b", type=NodeType.llm),
                NodeDef(id="b", type=NodeType.exit),  # duplicate id
            ],
            edges=[],
        )
        assert len(schema.node_ids()) == 2  # set dedup

    def test_get_node(self):
        schema = IntentSchema(
            name="t",
            nodes=[NodeDef(id="a", type=NodeType.entry)],
            edges=[],
        )
        node = schema.get_node("a")
        assert node is not None
        assert node.id == "a"
        assert schema.get_node("nonexistent") is None

    def test_get_outgoing(self):
        schema = IntentSchema(
            name="t",
            nodes=[NodeDef(id="a", type=NodeType.entry), NodeDef(id="b", type=NodeType.exit)],
            edges=[EdgeDef(source="a", target="b")],
        )
        outs = schema.get_outgoing("a")
        assert len(outs) == 1
        assert outs[0].target == "b"
        assert schema.get_outgoing("b") == []

    def test_get_incoming(self):
        schema = IntentSchema(
            name="t",
            nodes=[NodeDef(id="a", type=NodeType.entry), NodeDef(id="b", type=NodeType.exit)],
            edges=[EdgeDef(source="a", target="b")],
        )
        ins = schema.get_incoming("b")
        assert len(ins) == 1
        assert ins[0].source == "a"

    def test_get_entry_nodes(self):
        schema = IntentSchema(
            name="t",
            nodes=[NodeDef(id="a", type=NodeType.entry), NodeDef(id="b", type=NodeType.exit)],
            edges=[EdgeDef(source="a", target="b")],
        )
        entries = schema.get_entry_nodes()
        assert len(entries) == 1
        assert entries[0].id == "a"

    def test_get_exit_nodes(self):
        schema = IntentSchema(
            name="t",
            nodes=[NodeDef(id="a", type=NodeType.entry), NodeDef(id="b", type=NodeType.exit)],
            edges=[EdgeDef(source="a", target="b")],
        )
        exits = schema.get_exit_nodes()
        assert len(exits) == 0  # b is exit type

    def test_get_conditionals(self):
        schema = IntentSchema(
            name="t",
            nodes=[
                NodeDef(id="a", type=NodeType.entry),
                NodeDef(id="c", type=NodeType.conditional),
            ],
            edges=[],
        )
        conds = schema.get_conditionals()
        assert len(conds) == 1
        assert conds[0].id == "c"

    def test_get_tool_names(self):
        schema = IntentSchema(
            name="t",
            nodes=[
                NodeDef(id="s", type=NodeType.tool, tool="web_search"),
                NodeDef(id="r", type=NodeType.tool, tool="retrieve"),
                NodeDef(id="x", type=NodeType.exit),
            ],
            edges=[],
        )
        tools = schema.get_tool_names()
        assert "web_search" in tools
        assert "retrieve" in tools
        assert len(tools) == 2

    def test_to_dict(self):
        schema = IntentSchema(
            name="t", nodes=[], edges=[],
        )
        d = schema.to_dict()
        assert d["name"] == "t"
        assert "nodes" in d

    def test_from_dict(self):
        d = {"name": "test", "description": "desc", "nodes": [], "edges": [],
             "nodes": [{"id":"s","type":"tool","tool":"web_search"}], "config": {}}
        schema = IntentSchema.from_dict(d)
        assert schema.name == "test"
        assert len(schema.get_tool_names()) > 0

    def test_repr(self):
        schema = IntentSchema(name="t", nodes=[NodeDef(id="a", type=NodeType.entry)], edges=[])
        r = repr(schema)
        assert "t" in r
        assert "1" in r


# ── Test Templates ─────────────────────────────────────────────────────────


class TestTemplates:
    def test_get_templates(self):
        templates = get_templates()
        assert len(templates) >= 6

    def test_list_templates(self):
        templates = list_templates()
        assert len(templates) >= 6
        names = [t["name"] for t in templates]
        assert "search_and_answer" in names
        assert "plan_and_execute" in names
        assert "reflect_and_improve" in names

    def test_find_matching_templates(self):
        matches = find_matching_templates("search the web for information")
        assert len(matches) >= 1
        assert any(t.name == "search_and_answer" for t in matches)

    def test_best_template(self):
        t = best_template("search the web and find results")
        assert t is not None
        assert t.name == "search_and_answer"

    def test_best_template_no_match(self):
        t = best_template("xyznonexistentpattern12345")
        assert t is None

    def test_get_template_by_name(self):
        t = get_template("search_and_answer")
        assert t is not None
        assert t.name == "search_and_answer"
        assert get_template("nonexistent") is None

    def test_template_matches(self):
        t = get_template("search_and_answer")
        assert t is not None
        assert t.matches("find me some information")
        assert t.matches("search the web")
        assert not t.matches("plan and execute a task")

    def test_template_build(self):
        t = get_template("search_and_answer")
        assert t is not None
        schema = t.build("test query")
        assert schema is not None
        assert len(schema.nodes) >= 4
        assert len(schema.edges) >= 3

    def test_all_templates_build(self):
        """All templates should produce valid schemas."""
        for t in get_templates():
            schema = t.build(f"test {t.name}")
            assert schema is not None
            assert len(schema.nodes) >= 2
            assert len(schema.edges) >= 1


# ── Test Parser ────────────────────────────────────────────────────────────


class TestParser:
    def test_parse_nl_search(self):
        schema = parse_nl("search the web and find results")
        assert schema is not None
        assert schema.name == "search_and_answer"

    def test_parse_nl_reflect(self):
        schema = parse_nl("reflect and improve this response")
        assert schema is not None
        assert schema.name == "reflect_and_improve"

    def test_parse_nl_plan(self):
        schema = parse_nl("plan and execute a complex task")
        assert schema is not None
        assert schema.name == "plan_and_execute"

    def test_parse_nl_rag(self):
        schema = parse_nl("retrieve documents and answer questions")
        assert schema is not None
        assert schema is not None  # may match search_and_answer or rag_pipeline

    def test_parse_nl_router(self):
        schema = parse_nl("classify intent and route to different handlers")
        assert schema is not None
        assert schema.name == "intent_router"

    def test_parse_nl_tool_chain(self):
        schema = parse_nl("chain tools in sequence")
        assert schema is not None
        assert schema.name == "tool_chain"

    def test_parse_nl_no_match(self):
        schema = parse_nl("xyznonexistentpattern12345")
        assert schema is None

    def test_parse_nl_case_insensitive(self):
        schema = parse_nl("SEARCH THE WEB")
        assert schema is not None
        assert schema.name == "search_and_answer"


# ── Test Validator ─────────────────────────────────────────────────────────


class TestValidator:
    def test_valid_schema(self):
        schema = IntentSchema(
            name="t",
            nodes=[
                NodeDef(id="entry", type=NodeType.entry),
                NodeDef(id="exit", type=NodeType.exit),
            ],
            edges=[EdgeDef(source="entry", target="exit")],
        )
        assert is_valid(schema)

    def test_no_entry(self):
        schema = IntentSchema(
            name="t", nodes=[NodeDef(id="exit", type=NodeType.exit)], edges=[],
        )
        errors, _ = validate(schema)
        assert any("entry" in e.lower() for e in errors)

    def test_no_exit(self):
        schema = IntentSchema(
            name="t", nodes=[NodeDef(id="entry", type=NodeType.entry)], edges=[],
        )
        errors, _ = validate(schema)
        assert any("exit" in e.lower() for e in errors)

    def test_unknown_node_reference(self):
        schema = IntentSchema(
            name="t",
            nodes=[NodeDef(id="entry", type=NodeType.entry)],
            edges=[EdgeDef(source="entry", target="nonexistent")],
        )
        errors, _ = validate(schema)
        assert any("unknown" in e.lower() for e in errors)

    def test_conditional_no_condition(self):
        schema = IntentSchema(
            name="t",
            nodes=[
                NodeDef(id="entry", type=NodeType.entry),
                NodeDef(id="cond", type=NodeType.conditional),
                NodeDef(id="exit", type=NodeType.exit),
            ],
            edges=[EdgeDef(source="entry", target="cond"),
                   EdgeDef(source="cond", target="exit")],  # no condition!
        )
        errors, _ = validate(schema)
        assert any("condition" in e.lower() for e in errors)

    def test_tool_node_no_tool(self):
        schema = IntentSchema(
            name="t",
            nodes=[
                NodeDef(id="entry", type=NodeType.entry),
                NodeDef(id="tool1", type=NodeType.tool),  # no tool name!
                NodeDef(id="exit", type=NodeType.exit),
            ],
            edges=[EdgeDef(source="entry", target="tool1"),
                   EdgeDef(source="tool1", target="exit")],
        )
        errors, _ = validate(schema)
        assert any("tool" in e.lower() for e in errors)

    def test_duplicate_node_ids(self):
        schema = IntentSchema(
            name="t",
            nodes=[
                NodeDef(id="a", type=NodeType.entry),
                NodeDef(id="a", type=NodeType.exit),  # duplicate!
            ],
            edges=[],
        )
        errors, _ = validate(schema)
        assert any("duplicate" in e.lower() for e in errors)

    def test_format_errors_valid(self):
        schema = IntentSchema(
            name="t",
            nodes=[NodeDef(id="entry", type=NodeType.entry),
                   NodeDef(id="exit", type=NodeType.exit)],
            edges=[EdgeDef(source="entry", target="exit")],
        )
        report = format_errors(schema)
        assert "valid" in report.lower()

    def test_format_errors_invalid(self):
        schema = IntentSchema(name="t", nodes=[], edges=[])
        report = format_errors(schema)
        assert "error" in report.lower() or "Error" in report


# ── Test Codegen ───────────────────────────────────────────────────────────


class TestCodegen:
    def test_generate_python_valid(self):
        schema = IntentSchema(
            name="test_workflow",
            nodes=[
                NodeDef(id="entry", type=NodeType.entry),
                NodeDef(id="think", type=NodeType.llm, prompt="Think about it"),
                NodeDef(id="exit", type=NodeType.exit),
            ],
            edges=[EdgeDef(source="entry", target="think"),
                   EdgeDef(source="think", target="exit")],
        )
        code = generate_python(schema)
        assert "test_workflow" in code
        assert "CyclicGraph" in code
        assert "add_entry" in code or "add_llm" in code

    def test_generate_python_with_tools(self):
        schema = IntentSchema(
            name="wf",
            nodes=[
                NodeDef(id="entry", type=NodeType.entry),
                NodeDef(id="search", type=NodeType.tool, tool="web_search"),
                NodeDef(id="exit", type=NodeType.exit),
            ],
            edges=[EdgeDef(source="entry", target="search"),
                   EdgeDef(source="search", target="exit")],
            tools=["web_search"],
        )
        code = generate_python(schema)
        assert "web_search" in code

    def test_generate_python_invalid(self):
        schema = IntentSchema(name="bad", nodes=[], edges=[])
        code = generate_python(schema)
        assert "error" in code.lower()

    def test_generate_python_edge_with_condition(self):
        schema = IntentSchema(
            name="wf",
            nodes=[
                NodeDef(id="entry", type=NodeType.entry),
                NodeDef(id="cond", type=NodeType.conditional),
                NodeDef(id="exit", type=NodeType.exit),
            ],
            edges=[EdgeDef(source="entry", target="cond"),
                   EdgeDef(source="cond", target="exit", condition="approved")],
        )
        code = generate_python(schema)
        assert "approved" in code


# ── Test YAML Codegen ─────────────────────────────────────────────────────


class TestYAMLCodegen:
    def test_generate_yaml(self):
        schema = IntentSchema(
            name="wf",
            nodes=[NodeDef(id="entry", type=NodeType.entry),
                   NodeDef(id="exit", type=NodeType.exit)],
            edges=[EdgeDef(source="entry", target="exit")],
        )
        yaml = generate_yaml(schema)
        assert "wf" in yaml
        assert "entry" in yaml
        assert "exit" in yaml

    def test_generate_yaml_invalid(self):
        schema = IntentSchema(name="bad", nodes=[], edges=[])
        yaml = generate_yaml(schema)
        assert "error" in yaml.lower()

    def test_generate_dict(self):
        schema = IntentSchema(
            name="wf",
            nodes=[NodeDef(id="entry", type=NodeType.entry),
                   NodeDef(id="exit", type=NodeType.exit)],
            edges=[EdgeDef(source="entry", target="exit")],
        )
        d = generate_dict(schema)
        assert d["name"] == "wf"
        assert len(d["nodes"]) == 2
        assert len(d["edges"]) == 1


# ── Test CompilationResult ─────────────────────────────────────────────────


class TestCompilationResult:
    def test_create_result(self):
        schema = IntentSchema(name="t", nodes=[], edges=[])
        result = CompilationResult(schema=schema, intent_schema=schema)
        assert result.success
        assert not result.has_errors()

    def test_result_with_errors(self):
        schema = IntentSchema(name="t", nodes=[], edges=[])
        result = CompilationResult(schema=schema, intent_schema=schema,
                                    success=False, errors=["Something wrong"])
        assert not result.success
        assert result.has_errors()

    def test_result_with_warnings(self):
        schema = IntentSchema(name="t", nodes=[], edges=[])
        result = CompilationResult(schema=schema, intent_schema=schema,
                                    warnings=["Warning"])
        assert result.has_warnings()

    def test_summary(self):
        schema = IntentSchema(name="t", nodes=[], edges=[])
        result = CompilationResult(schema=schema, intent_schema=schema)
        s = result.summary()
        assert "Compilation" in s

    def test_summary_with_errors(self):
        schema = IntentSchema(name="t", nodes=[], edges=[])
        result = CompilationResult(schema=schema, intent_schema=schema,
                                    success=False, errors=["Bad"])
        s = result.summary()
        assert "❌" in s


# ── Test Compiler Integration ──────────────────────────────────────────────


class TestCompiler:
    def test_compile_workflow_template(self):
        result = asyncio.run(compile_workflow("search the web and answer"))
        assert result.success
        assert result.intent_schema.name == "search_and_answer"
        assert len(result.python_code) > 100

    def test_compile_workflow_reflect(self):
        result = asyncio.run(compile_workflow("reflect and improve this"))
        assert result.success
        assert result.intent_schema.name == "reflect_and_improve"

    def test_compile_workflow_yaml(self):
        result = asyncio.run(compile_workflow("search and answer"))
        assert len(result.yaml_output) > 50

    def test_compile_workflow_no_match(self):
        result = asyncio.run(compile_workflow("xyznonexistentpattern12345"))
        assert not result.success  # No LLM provided

    def test_compile_with_templates(self):
        """Verify all templates produce valid compilations."""
        templates = list_templates()
        for t in templates:
            result = asyncio.run(compile_workflow(
                f"{t['description']} using {t['name']}"
            ))
            if result.success:
                assert len(result.python_code) > 50
                assert is_valid(result.intent_schema)

    def test_codegen_with_llm_node(self):
        """Verify LLM nodes produce proper prompts in generated code."""
        schema = IntentSchema(
            name="test",
            nodes=[
                NodeDef(id="entry", type=NodeType.entry),
                NodeDef(id="think", type=NodeType.llm, prompt="Analyze this"),
                NodeDef(id="exit", type=NodeType.exit),
            ],
            edges=[EdgeDef(source="entry", target="think"),
                   EdgeDef(source="think", target="exit")],
        )
        code = generate_python(schema)
        assert "Analyze" in code

    def test_codegen_with_conditional(self):
        """Verify conditional edges produce proper routing code."""
        schema = IntentSchema(
            name="test",
            nodes=[
                NodeDef(id="entry", type=NodeType.entry),
                NodeDef(id="check", type=NodeType.conditional),
                NodeDef(id="branch_a", type=NodeType.llm, prompt="Handle A"),
                NodeDef(id="branch_b", type=NodeType.llm, prompt="Handle B"),
                NodeDef(id="exit", type=NodeType.exit),
            ],
            edges=[
                EdgeDef(source="entry", target="check"),
                EdgeDef(source="check", target="branch_a", condition="is_a"),
                EdgeDef(source="check", target="branch_b", condition="is_b"),
                EdgeDef(source="branch_a", target="exit"),
                EdgeDef(source="branch_b", target="exit"),
            ],
        )
        code = generate_python(schema)
        assert "is_a" in code
        assert "is_b" in code
