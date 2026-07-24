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
"""Agent Visual Debugger — interactive debugging UI for agent execution.

Provides:
  - DebugSession: wraps Agent + TimeTravelDebugger with pause/step/resume
  - DebuggerAPI: FastAPI router for REST + WebSocket endpoints
  - Web frontend: real-time timeline, state inspector, breakpoints, branching

Usage:
    from chainforge.debugger import DebugSession, DebuggerAPI

    session = DebugSession(agent=my_agent, name="debug-1")
    async for event in session.run("Hello"):
        ...

    # Or via the web API:
    debug_api = DebuggerAPI()
    app.include_router(debug_api.router, prefix="/api/v1/debug")
"""

from chainforge.debugger.session import DebugSession, Breakpoint, SessionStatus
from chainforge.debugger.api import DebuggerAPI

__all__ = [
    "DebugSession",
    "Breakpoint",
    "SessionStatus",
    "DebuggerAPI",
]
