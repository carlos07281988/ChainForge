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
]
