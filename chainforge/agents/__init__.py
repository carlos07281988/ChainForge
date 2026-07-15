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
"""Agent pattern variants + linking capabilities."""

from chainforge.agents.react import ReActAgent
from chainforge.agents.tool_agent import ToolAgent
from chainforge.agents.plan_execute import PlanAndExecute
from chainforge.agents.reflection import Reflection
from chainforge.agents.self_ask import SelfAsk
from chainforge.agents.tree_of_thoughts import TreeOfThoughts
from chainforge.agents.chain_of_thought import ChainOfThought
from chainforge.agents.conversational import ConversationalAgent
from chainforge.agents.router import RouterAgent
from chainforge.agents.agent_tool import AgentTool
from chainforge.agents.agent_chain import AgentChain, ChainTool
from chainforge.agents.agent_hub import AgentHub

__all__ = [
    "ReActAgent", "ToolAgent",
    "PlanAndExecute", "Reflection", "SelfAsk",
    "TreeOfThoughts", "ChainOfThought",
    "ConversationalAgent", "RouterAgent",
    "AgentTool", "AgentChain", "ChainTool", "AgentHub",
]

from chainforge.agents.self_evolving import SelfEvolvingAgent, ExecutionMetrics

__all__.extend(["SelfEvolvingAgent", "ExecutionMetrics"])
