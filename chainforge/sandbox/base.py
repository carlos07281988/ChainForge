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
