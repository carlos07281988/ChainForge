"""ChainForge — 锻造链: A next-generation agent framework.

Craft your LLM call chains, tool chains, and processing chains
with a clean, streaming-first, type-safe design.
"""

from chainforge._version import __version__

from chainforge.core.llm import LLM, LLMResponse
from chainforge.core.tool import Tool, tool
from chainforge.core.message import Message, ToolCall, ToolResult
from chainforge.core.stream import StreamEvent, Stream
from chainforge.core.agent import Agent
from chainforge.core.pipeline import Pipeline
from chainforge.core.middleware import Middleware

__all__ = [
    "__version__",
    "LLM", "LLMResponse",
    "Tool", "tool",
    "Message", "ToolCall", "ToolResult",
    "StreamEvent", "Stream",
    "Agent",
    "Pipeline",
    "Middleware",
]
