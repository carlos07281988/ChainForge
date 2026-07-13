"""Agent pattern variants — beyond the core Agent loop."""

from chainforge.agents.react import ReActAgent
from chainforge.agents.tool_agent import ToolAgent
from chainforge.agents.plan_execute import PlanAndExecute
from chainforge.agents.reflection import Reflection
from chainforge.agents.self_ask import SelfAsk

__all__ = ["ReActAgent", "ToolAgent", "PlanAndExecute", "Reflection", "SelfAsk"]
