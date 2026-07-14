# Copyright 2024 ChainForge Contributors
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
"""Tests for toolkits."""
from chainforge.tools.toolkits import ToolKit, calculator_toolkit, file_toolkit, web_toolkit
from chainforge.core.tool import Tool


class TestToolKit:
    def test_creation(self):
        tk = ToolKit(name="test", tools=[], description="Test toolkit")
        assert tk.name == "test"
        assert tk.tools == []

    def test_add_tool(self):
        tk = ToolKit(name="test", tools=[])
        tk.add_tool(lambda: None)
        assert len(tk.tools) == 1

    def test_tools_property_returns_copy(self):
        tk = ToolKit(name="test", tools=[1, 2])
        tools = tk.tools
        tools.append(3)
        assert len(tk.tools) == 2  # Original unchanged


class TestCalculatorToolkit:
    def test_tools_count(self):
        tk = calculator_toolkit()
        assert len(tk.tools) >= 3
        assert tk.name == "calculator"

    def test_tools_are_callable(self):
        tk = calculator_toolkit()
        for t in tk.tools:
            assert callable(t)


class TestFileToolkit:
    def test_tools_count(self):
        tk = file_toolkit()
        assert len(tk.tools) >= 2
        assert tk.name == "file"


class TestWebToolkit:
    def test_creation(self):
        tk = web_toolkit()
        assert tk.name == "web"
        assert len(tk.tools) >= 1
