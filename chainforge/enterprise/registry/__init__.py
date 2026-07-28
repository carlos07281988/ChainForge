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
"""Agent Capability Registry — DNS for Agents: register, discover, negotiate, version."""

from chainforge.enterprise.registry.profile import AgentProfile, ServiceLevelAgreement
from chainforge.enterprise.registry.registry import CapabilityRegistry
from chainforge.enterprise.registry.discovery import CapabilityQuery
from chainforge.enterprise.registry.negotiation import AutoNegotiation, NegotiationResult

__all__ = [
    "AgentProfile",
    "ServiceLevelAgreement",
    "CapabilityRegistry",
    "CapabilityQuery",
    "AutoNegotiation",
    "NegotiationResult",
]
