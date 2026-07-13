"""Agent pattern variants — beyond the core Agent loop."""

from chainforge.agents.react import ReActAgent
from chainforge.agents.tool_agent import ToolAgent
from chainforge.agents.plan_execute import PlanAndExecute
from chainforge.agents.reflection import Reflection
from chainforge.agents.self_ask import SelfAsk
from chainforge.agents.tree_of_thoughts import TreeOfThoughts
from chainforge.agents.chain_of_thought import ChainOfThought
from chainforge.agents.conversational import ConversationalAgent
from chainforge.agents.router import RouterAgent

__all__ = [
    "ReActAgent", "ToolAgent",
    "PlanAndExecute", "Reflection", "SelfAsk",
    "TreeOfThoughts", "ChainOfThought",
    "ConversationalAgent", "RouterAgent",
]
