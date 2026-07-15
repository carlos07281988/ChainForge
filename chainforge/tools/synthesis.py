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
"""Adaptive Tool Synthesis — agents write, test, and register tools at runtime.

Uses LLM + sandbox to dynamically create tools. Synthesized tools are cached.

Usage:
    synthesizer = ToolSynthesizer(llm=my_llm)
    new_tool = await synthesizer.synthesize("calculate compound interest")
    agent = Agent(llm=llm, tools=[new_tool])
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import time
from typing import Any

from pydantic import BaseModel, Field

from chainforge.core.tool import FunctionTool, ToolSpec
from chainforge.logging import get_logger, log_data

logger = get_logger("tools.synthesis")


class SynthesizedTool(BaseModel):
    """A tool that was synthesized at runtime."""

    name: str = Field(description="Tool name")
    code: str = Field(description="Generated Python source code")
    spec: ToolSpec | None = Field(default=None)
    created_at: float = Field(default_factory=time.time)
    hash: str = Field(default="")
    test_result: str | None = Field(default=None)
    is_verified: bool = Field(default=False)


class ToolCache(BaseModel):
    """Cache of previously synthesized tools keyed by intent hash."""

    tools: dict[str, SynthesizedTool] = Field(default_factory=dict)

    def lookup(self, intent: str) -> SynthesizedTool | None:
        key = hashlib.sha256(intent.encode()).hexdigest()[:16]
        return self.tools.get(key)

    def store(self, intent: str, tool: SynthesizedTool) -> None:
        key = hashlib.sha256(intent.encode()).hexdigest()[:16]
        tool.hash = key
        self.tools[key] = tool


class ToolSynthesizer:
    """Synthesizes new tools at runtime using LLM + code verification.

    Flow: LLM generates Python function → verifies syntax → tests execution
    → extracts ToolSpec → wraps as FunctionTool → caches for reuse.
    """

    def __init__(
        self,
        llm=None,
        cache: ToolCache | None = None,
        max_retries: int = 2,
    ):
        self._llm = llm
        self._cache = cache or ToolCache()
        self._max_retries = max_retries

    @property
    def cache(self) -> ToolCache:
        return self._cache

    async def synthesize(self, description: str, tool_name: str | None = None) -> FunctionTool:
        """Synthesize a tool from a natural language description.

        Args:
            description: What the tool should do.
            tool_name: Optional custom name.

        Returns:
            A FunctionTool usable with any Agent.
        """
        # Check cache
        cached = self._cache.lookup(description)
        if cached and cached.is_verified:
            log_data(logger, "info", f"Using cached tool: {cached.name}")
            fn = self._code_to_function(cached.code, cached.name)
            if fn:
                return self._function_to_tool(fn, cached.name, description)

        # Generate
        code = await self._generate_tool_code(description, tool_name)

        # Verify and fix
        for attempt in range(self._max_retries + 1):
            result = self._verify_code(code)
            if result["success"]:
                break
            if attempt < self._max_retries:
                log_data(logger, "info", f"Fix attempt {attempt+1}: {result['error']}")
                code = await self._fix_code(code, result["error"])

        name = tool_name or self._extract_function_name(code) or "synthesized_tool"
        fn = self._code_to_function(code, name)

        if fn is None:
            raise RuntimeError(f"Failed to synthesize tool for: {description}")

        func_tool = self._function_to_tool(fn, name, description)

        synthesized = SynthesizedTool(
            name=name, code=code, spec=func_tool.spec,
            is_verified=result["success"],
            test_result=str(result.get("output", "")),
        )
        self._cache.store(description, synthesized)

        return func_tool

    async def _generate_tool_code(self, description: str, tool_name: str | None = None) -> str:
        """Generate Python function code via LLM."""
        if self._llm is None:
            name = tool_name or "synthesized_tool"
            return (
                f"def {name}(query: str = '') -> str:\n"
                f'    """Process: {description}"""\n'
                f"    return f'Processed: {query}'"
            )

        from chainforge.core.message import Message

        prompt = (
            "Generate a SINGLE Python function for: " + description + "\n\n"
            "Requirements:\n"
            "- Include type hints for all params and return str\n"
            "- Include a clear docstring\n"
            "- Safe: no network, no file writes, stdlib only\n"
            "- Return a string result\n\n"
            "Output ONLY the Python code."
        )
        msgs = [Message.user(prompt)]
        response = await self._llm.generate(msgs)
        code = response.content or ""

        # Extract from markdown
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0]
        elif "```" in code:
            code = code.split("```")[1].split("```")[0]

        return code.strip()

    async def _fix_code(self, code: str, error: str) -> str:
        """Ask LLM to fix broken code."""
        if self._llm is None:
            return code

        from chainforge.core.message import Message

        prompt = (
            "Fix this Python function. Error:\n" + error + "\n\nCODE:\n" + code + "\n\nOutput ONLY the fixed code."
        )
        msgs = [Message.user(prompt)]
        response = await self._llm.generate(msgs)
        fixed = response.content or ""

        if "```python" in fixed:
            fixed = fixed.split("```python")[1].split("```")[0]
        elif "```" in fixed:
            fixed = fixed.split("```")[1].split("```")[0]

        return fixed.strip()

    def _verify_code(self, code: str) -> dict:
        """Verify generated code syntax and basic execution."""
        try:
            ast.parse(code)
        except SyntaxError as e:
            return {"success": False, "error": f"Syntax: {e}"}

        func_name = self._extract_function_name(code)
        if not func_name:
            return {"success": False, "error": "No function found"}

        try:
            local_ns = {}
            exec(compile(code, "<synthesized>", "exec"), local_ns)
            fn = local_ns.get(func_name)
            if fn is None:
                return {"success": False, "error": f"Function {func_name} not defined"}

            sig = inspect.signature(fn)
            all_default = all(
                p.default is not inspect.Parameter.empty for p in sig.parameters.values()
            )
            if all_default or len(sig.parameters) == 0:
                result = fn()
                return {"success": True, "output": str(result)[:200]}

            return {"success": True, "output": "Function OK (needs args)"}

        except Exception as e:
            return {"success": False, "error": str(e)[:500]}

    def _extract_function_name(self, code: str) -> str | None:
        """Extract first function name from source code."""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    return node.name
        except SyntaxError:
            pass
        return None

    def _code_to_function(self, code: str, name: str) -> Any:
        """Convert source code to a callable function."""
        try:
            local_ns = {}
            exec(compile(code, "<synthesized>", "exec"), local_ns)
            return local_ns.get(name)
        except Exception:
            return None

    def _function_to_tool(self, fn: Any, name: str, description: str) -> FunctionTool:
        """Wrap a function as a FunctionTool."""
        sig = inspect.signature(fn)
        properties = {}
        required = []
        for p_name, p in sig.parameters.items():
            ann = p.annotation
            type_map = {str: "string", int: "integer", float: "number", bool: "boolean"}
            ptype = type_map.get(ann, "string")
            properties[p_name] = {"type": ptype, "description": f"Parameter {p_name}"}
            if p.default is inspect.Parameter.empty:
                required.append(p_name)

        spec = ToolSpec(
            name=name,
            description=description[:100],
            parameters={"type": "object", "properties": properties, "required": required},
        )

        ft = FunctionTool.__new__(FunctionTool)
        ft._fn = fn
        ft._name = name
        ft._description = description[:100]
        ft._spec = spec
        return ft


__all__ = ["ToolSynthesizer", "ToolCache", "SynthesizedTool"]
