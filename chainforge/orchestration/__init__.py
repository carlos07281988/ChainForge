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
"""Multi-agent orchestration — coordinate multiple agents to solve complex tasks.

Provides:
  - Swarm: parallel/sequential/conference execution
  - Supervisor: hierarchical delegation
  - AgentNetwork: peer-to-peer messaging
  - Debate: structured argumentation
"""

from chainforge.orchestration.swarm import Swarm, SwarmMode
from chainforge.orchestration.supervisor import Supervisor
from chainforge.orchestration.network import AgentNetwork
from chainforge.orchestration.debate import Debate, DebateAgent

__all__ = [
    "Swarm", "SwarmMode",
    "Supervisor",
    "AgentNetwork",
    "Debate", "DebateAgent",
]

from chainforge.orchestration.consensus import ConsensusAgent, ConsensusStrategy, ConsensusResult, ModelVote

__all__.extend(["ConsensusAgent", "ConsensusStrategy", "ConsensusResult", "ModelVote"])
