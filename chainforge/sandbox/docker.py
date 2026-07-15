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
"""Docker sandbox — execute code in isolated Docker containers.

Requires Docker to be running on the host system.
Uses the `docker` Python SDK (pip install docker).

Usage:
    from chainforge.sandbox import DockerSandbox

    sandbox = DockerSandbox(image="python:3.11-slim", timeout=30)
    result = await sandbox.execute("print('hello world')", "python")
    print(result.stdout)
"""

from __future__ import annotations

import os
import tempfile
import textwrap
import time
import uuid
from logging import DEBUG, WARNING
from pathlib import Path

from chainforge.logging import get_logger, log_data
from chainforge.sandbox.base import Sandbox, SandboxResult

logger = get_logger("sandbox.docker")

DEFAULT_IMAGES = {
    "python": "python:3.11-slim",
    "bash": "ubuntu:22.04",
    "sh": "ubuntu:22.04",
    "node": "node:20-slim",
    "go": "golang:1.22",
    "rust": "rust:1.77-slim",
}


class DockerSandbox:
    """Execute code in a Docker container with full isolation.

    Each execution creates a temporary container that is removed after completion.
    Provides container-level isolation: filesystem, process, network, memory.

    Args:
        image: Docker image (or dict mapping language to image).
        timeout: Max execution time in seconds (default 60).
        memory_limit: Memory limit (e.g. "512m", "1g"). None = no limit.
        network_disabled: Disable network access (default True for safety).
        remove_after: Remove container after execution (default True).
        docker_host: Docker daemon socket (default from environment).
    """

    def __init__(
        self,
        image: str | dict[str, str] | None = None,
        timeout: int = 60,
        memory_limit: str | None = "512m",
        network_disabled: bool = True,
        remove_after: bool = True,
        docker_host: str | None = None,
    ):
        self._image_config = image or DEFAULT_IMAGES
        self.timeout = timeout
        self.memory_limit = memory_limit
        self.network_disabled = network_disabled
        self.remove_after = remove_after
        self.docker_host = docker_host

    def _get_client(self):
        try:
            import docker
        except ImportError:
            raise ImportError(
                "DockerSandbox requires the `docker` package. Install: pip install docker"
            )
        kwargs = {}
        if self.docker_host:
            kwargs["base_url"] = self.docker_host
        return docker.from_env(**kwargs)

    def _resolve_image(self, language: str) -> str:
        if isinstance(self._image_config, dict):
            return self._image_config.get(language, self._image_config.get("python", "python:3.11-slim"))
        return self._image_config

    async def execute(self, code: str, language: str = "python") -> SandboxResult:
        start = time.monotonic()
        image = self._resolve_image(language)
        log_data(logger, DEBUG, f"Docker sandbox exec", data={
            "language": language, "image": image,
            "code_length": len(code), "timeout": self.timeout,
        })

        container_name = f"chainforge-sandbox-{uuid.uuid4().hex[:8]}"

        try:
            client = self._get_client()

            # Write code to a temp file for mounting
            ext_map = {
                "python": ".py", "bash": ".sh", "sh": ".sh",
                "node": ".js", "go": ".go", "rust": ".rs",
            }
            ext = ext_map.get(language, ".txt")
            tmp_dir = tempfile.mkdtemp(prefix="chainforge_sandbox_")
            code_file = Path(tmp_dir) / f"script{ext}"
            code_file.write_text(code, encoding="utf-8")

            # Command to run based on language
            cmd_map = {
                "python": ["python", f"/mnt/script{ext}"],
                "bash": ["bash", f"/mnt/script{ext}"],
                "sh": ["sh", f"/mnt/script{ext}"],
                "node": ["node", f"/mnt/script{ext}"],
                "go": ["go", "run", f"/mnt/script{ext}"],
                "rust": ["rustc", f"/mnt/script{ext}", "-o", "/mnt/output", "&&", "/mnt/output"],
            }
            cmd = cmd_map.get(language, ["python", f"/mnt/script{ext}"])

            container_kwargs = {
                "image": image,
                "command": cmd,
                "volumes": {tmp_dir: {"bind": "/mnt", "mode": "ro"}},
                "working_dir": "/mnt",
                "detach": True,
                "network_disabled": self.network_disabled,
                "remove": self.remove_after,
                "name": container_name,
            }
            if self.memory_limit:
                container_kwargs["mem_limit"] = self.memory_limit

            container = client.containers.create(**container_kwargs)
            container.start()

            # Wait for completion with timeout
            exit_code = None
            try:
                result = container.wait(timeout=self.timeout)
                exit_code = result.get("StatusCode", 0) or 0
            except Exception:
                # Timeout or wait error
                container.kill()
                exit_code = 124

            # Get logs
            stdout = ""
            stderr = ""
            try:
                log_output = container.logs(stdout=True, stderr=False, tail=500).decode(errors="replace")
                if log_output:
                    stdout = log_output[:100_000]
                err_output = container.logs(stdout=False, stderr=True, tail=500).decode(errors="replace")
                if err_output:
                    stderr = err_output[:100_000]
            except Exception:
                pass

            # Cleanup
            try:
                container.remove(force=True)
            except Exception:
                pass

            # Cleanup temp dir
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

            duration = round(time.monotonic() - start, 3)

            if exit_code == 124:
                return SandboxResult(
                    stderr=f"Execution timed out after {self.timeout}s",
                    exit_code=124, duration_s=duration,
                )

            return SandboxResult(
                stdout=stdout, stderr=stderr, exit_code=exit_code, duration_s=duration,
            )

        except ImportError as e:
            return SandboxResult(stderr=str(e), exit_code=1, duration_s=round(time.monotonic() - start, 3))
        except Exception as e:
            log_data(logger, WARNING, f"Docker sandbox failed: {e}")
            return SandboxResult(
                stderr=f"Docker execution error: {e}",
                exit_code=1, duration_s=round(time.monotonic() - start, 3),
            )
