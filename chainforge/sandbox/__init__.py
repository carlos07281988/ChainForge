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
