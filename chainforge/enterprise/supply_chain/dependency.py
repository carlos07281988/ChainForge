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
"""DependencyAnalyzer — analyze tool/skill import chains."""
from __future__ import annotations

import ast
import inspect
from typing import Any

from pydantic import BaseModel, Field


class DepInfo(BaseModel):
    """Information about a single dependency."""
    name: str = ""
    module_path: str = ""
    imports: list[str] = Field(default_factory=list)
    source_file: str = ""


class DependencyAnalyzer:
    """Analyze the import chain of a tool or callable.

    Usage:
        analyzer = DependencyAnalyzer()
        info = analyzer.analyze(my_tool_function)
        # -> DepInfo(name="my_tool", imports=["os", "requests", "smtplib"], ...)
    """

    def analyze(self, obj: Any) -> DepInfo:
        """Extract the import dependencies of a callable or tool object."""
        name = getattr(obj, "__name__", getattr(obj, "name", str(obj)))
        module_path = getattr(obj, "__module__", "unknown")
        imports: list[str] = []
        source_file = ""

        try:
            mod = inspect.getmodule(obj)
            if mod is not None and hasattr(mod, "__file__") and mod.__file__:
                source_file = mod.__file__
                try:
                    with open(source_file) as f:
                        tree = ast.parse(f.read())
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                imports.append(alias.name.split(".")[0])
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                imports.append(node.module.split(".")[0])
                except (OSError, SyntaxError):
                    pass
            else:
                # Fallback: try to inspect the function's source
                try:
                    src = inspect.getsource(obj)
                    tree = ast.parse(src)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                imports.append(alias.name.split(".")[0])
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                imports.append(node.module.split(".")[0])
                except (OSError, TypeError):
                    pass
        except Exception:
            pass

        return DepInfo(
            name=name,
            module_path=module_path,
            imports=sorted(set(imports)),
            source_file=source_file,
        )
