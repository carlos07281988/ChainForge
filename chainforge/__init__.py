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
"""ChainForge — 锻造链: A next-generation agent framework."""
"""ChainForge — 锻造链: A next-generation agent framework.

Submodules:
  chainforge.a2a — Agent-to-Agent protocol (Google A2A)
"""

from chainforge._version import __version__
from chainforge.core.llm import LLM, LLMResponse
from chainforge.core.tool import Tool, tool
from chainforge.core.message import Message, ToolCall, ToolResult
from chainforge.core.stream import StreamEvent, Stream
from chainforge.core.agent import Agent
from chainforge.core.pipeline import Pipeline
from chainforge.core.middleware import Middleware
from chainforge.core.graph import DAG
from chainforge.core.human_in_loop import HumanInTheLoop, ApprovalRequest, ApprovalDecision
from chainforge.core.state import AgentState, StateTracker, StateTransition
from chainforge.logging import configure_logging, get_logger, log_data
from chainforge import a2a as a2a
from chainforge import sandbox as sandbox
from chainforge import config as config
from chainforge.core.files import FileLoader, FileContent, load_file, load_image

__all__ = [
    "__version__",
    "LLM", "LLMResponse",
    "Tool", "tool",
    "Message", "ToolCall", "ToolResult",
    "StreamEvent", "Stream",
    "Agent",
    "Pipeline",
    "DAG",
    "Middleware",
    "HumanInTheLoop", "ApprovalRequest", "ApprovalDecision",
    "AgentState", "StateTracker", "StateTransition",
    "configure_logging", "get_logger", "log_data",
    "a2a",
    "sandbox",
    "config",
    "FileLoader", "FileContent",
    "load_file", "load_image",
]
