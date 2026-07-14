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
"""Sandbox protocol and result type for safe code execution."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field


class SandboxResult(BaseModel):
    """Result of executing code in a sandbox."""

    stdout: str = Field(default="", description="Standard output")
    stderr: str = Field(default="", description="Standard error")
    exit_code: int = Field(default=0, description="Exit code (0 = success)")
    duration_s: float = Field(default=0.0, description="Execution time in seconds")
    files: list = Field(default_factory=list, description="Files generated during execution")


class Sandbox(Protocol):
    """Isolated execution environment for running untrusted code."""

    async def execute(self, code: str, language: str = "python") -> SandboxResult:
        """Execute *code* in the sandbox and return the result.

        Args:
            code: Source code to execute.
            language: Language identifier ("python", "bash", "sh", etc.).

        Returns:
            SandboxResult with stdout, stderr, and exit code.
        """
        ...
