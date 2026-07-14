"""Tests for the sandbox module."""

import pytest
from chainforge.sandbox import SandboxResult, SubprocessSandbox


class TestSandboxResult:
    def test_defaults(self):
        r = SandboxResult()
        assert r.stdout == ""
        assert r.stderr == ""
        assert r.exit_code == 0
        assert r.duration_s == 0.0
        assert r.files == []


class TestSubprocessSandbox:
    @pytest.mark.asyncio
    async def test_execute_python_success(self):
        sandbox = SubprocessSandbox(timeout=5)
        result = await sandbox.execute("print('hello world')", "python")
        assert result.exit_code == 0
        assert "hello world" in result.stdout
        assert result.duration_s >= 0

    @pytest.mark.asyncio
    async def test_execute_python_error(self):
        sandbox = SubprocessSandbox(timeout=5)
        result = await sandbox.execute("1/0", "python")
        assert result.exit_code != 0
        assert "ZeroDivisionError" in result.stderr or "ZeroDivisionError" in result.stdout

    @pytest.mark.asyncio
    async def test_execute_bash(self):
        sandbox = SubprocessSandbox(timeout=5)
        result = await sandbox.execute("echo 'hello from bash'", "bash")
        assert result.exit_code == 0
        assert "hello from bash" in result.stdout

    @pytest.mark.asyncio
    async def test_execute_bash_error(self):
        sandbox = SubprocessSandbox(timeout=5)
        result = await sandbox.execute("exit 42", "bash")
        assert result.exit_code == 42

    @pytest.mark.asyncio
    async def test_unsupported_language(self):
        sandbox = SubprocessSandbox(timeout=5)
        result = await sandbox.execute("code", "brainfuck")
        assert result.exit_code == 1
        assert "Unsupported language" in result.stderr

    @pytest.mark.asyncio
    async def test_timeout(self):
        sandbox = SubprocessSandbox(timeout=1)
        result = await sandbox.execute("import time; time.sleep(10)", "python")
        assert result.exit_code == 124
        assert "timed out" in result.stderr

    def test_reuse_sandbox(self):
        sandbox = SubprocessSandbox(timeout=5)
        import asyncio
        r1 = asyncio.run(sandbox.execute("print('first')", "python"))
        r2 = asyncio.run(sandbox.execute("print('second')", "python"))
        assert r1.exit_code == 0
        assert r2.exit_code == 0
        assert "first" in r1.stdout
        assert "second" in r2.stdout
