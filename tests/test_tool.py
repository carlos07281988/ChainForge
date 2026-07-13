"""Tests for the tool module."""

import pytest

from chainforge.core.tool import tool, FunctionTool, ToolSpec


class TestFunctionTool:
    def test_tool_decorator_no_args(self):
        @tool
        def my_func(x: str) -> str:
            """A test function."""
            return f"hello {x}"

        assert isinstance(my_func, FunctionTool)
        assert my_func.spec.name == "my_func"
        assert my_func.spec.description == "A test function."

    def test_tool_decorator_with_args(self):
        @tool(name="custom_name", description="Custom description")
        def my_func(x: str) -> str:
            return f"hello {x}"

        assert my_func.spec.name == "custom_name"
        assert "Custom description" in my_func.spec.description

    def test_tool_spec_generation(self):
        @tool
        def search(query: str, limit: int = 10) -> str:
            """Search for something."""
            return f"searching for {query}"

        spec = search.spec
        assert spec.name == "search"
        props = spec.parameters["properties"]
        assert "query" in props
        assert "limit" in props
        assert "query" in spec.parameters["required"]
        assert "limit" not in spec.parameters["required"]

    def test_tool_run_sync(self):
        @tool
        def add(a: int, b: int) -> str:
            return str(a + b)

        import asyncio
        result = asyncio.run(add.run(a=3, b=4))
        assert result == "7"

    def test_tool_no_docstring(self):
        @tool
        def simple():
            pass

        assert simple.spec.description == ""

    def test_type_mapping(self):
        @tool
        def mixed(a: str, b: int, c: float, d: bool) -> str:
            return "ok"

        props = mixed.spec.parameters["properties"]
        assert props["a"]["type"] == "string"
        assert props["b"]["type"] == "integer"
        assert props["c"]["type"] == "number"
        assert props["d"]["type"] == "boolean"


class TestToolSpec:
    def test_tool_spec_defaults(self):
        spec = ToolSpec(name="test")
        assert spec.name == "test"
        assert spec.description == ""
        assert spec.parameters["type"] == "object"

    def test_tool_spec_with_params(self):
        spec = ToolSpec(
            name="test",
            description="A test tool",
            parameters={
                "type": "object",
                "properties": {"x": {"type": "string"}},
                "required": ["x"],
            },
        )
        assert spec.description == "A test tool"
        assert "x" in spec.parameters["properties"]
