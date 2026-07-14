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
"""Subprocess-based sandbox — executes code in a local child process.

⚠️  This provides process-level isolation only (no container/VM).
Use the DockerSandbox for production workloads.
"""

from __future__ import annotations

import asyncio
import sys
import time
from logging import DEBUG, WARNING

from chainforge.logging import get_logger, log_data
from chainforge.sandbox.base import Sandbox, SandboxResult

logger = get_logger("sandbox.subprocess")


class SubprocessSandbox:
    """Execute code in a local subprocess with timeout and resource limits.

    Safe for development and testing. For production, use DockerSandbox.

    Args:
        timeout: Maximum execution time in seconds (default 30).
        max_output: Maximum output characters (default 100_000).
    """

    def __init__(self, timeout: int = 30, max_output: int = 100_000):
        self.timeout = timeout
        self.max_output = max_output

    async def execute(self, code: str, language: str = "python") -> SandboxResult:
        start = time.monotonic()
        log_data(logger, DEBUG, f"Executing {language} code", data={"length": len(code), "timeout": self.timeout})

        try:
            if language in ("python", "py"):
                result = await self._run_python(code)
            elif language in ("bash", "sh", "shell"):
                result = await self._run_shell(code)
            else:
                result = SandboxResult(stderr=f"Unsupported language: {language}", exit_code=1)

            result.duration_s = round(time.monotonic() - start, 3)
            log_data(logger, DEBUG, f"Execution complete", data={"exit_code": result.exit_code, "duration": result.duration_s})
            return result

        except asyncio.TimeoutError:
            log_data(logger, WARNING, f"Execution timed out ({self.timeout}s)")
            return SandboxResult(
                stderr=f"Execution timed out after {self.timeout}s",
                exit_code=124,
                duration_s=round(time.monotonic() - start, 3),
            )
        except Exception as e:
            log_data(logger, WARNING, f"Execution failed: {e}")
            return SandboxResult(
                stderr=f"Execution error: {e}",
                exit_code=1,
                duration_s=round(time.monotonic() - start, 3),
            )

    async def _run_python(self, code: str) -> SandboxResult:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-c", code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise

        return SandboxResult(
            stdout=stdout.decode(errors="replace")[:self.max_output],
            stderr=stderr.decode(errors="replace")[:self.max_output],
            exit_code=proc.returncode or 0,
        )

    async def _run_shell(self, code: str) -> SandboxResult:
        proc = await asyncio.create_subprocess_shell(
            code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise

        return SandboxResult(
            stdout=stdout.decode(errors="replace")[:self.max_output],
            stderr=stderr.decode(errors="replace")[:self.max_output],
            exit_code=proc.returncode or 0,
        )
