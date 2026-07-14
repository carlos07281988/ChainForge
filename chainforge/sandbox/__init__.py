"""Sandbox — safe code execution environments for agents.

Provides isolated execution for Python, shell, and other languages.

Usage:
    from chainforge.sandbox import SubprocessSandbox

    sandbox = SubprocessSandbox(timeout=30)
    result = await sandbox.execute("print('hello')", "python")
    print(result.stdout)
"""

from chainforge.sandbox.base import Sandbox, SandboxResult
from chainforge.sandbox.subprocess import SubprocessSandbox

__all__ = ["Sandbox", "SandboxResult", "SubprocessSandbox"]
