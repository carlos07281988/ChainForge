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
"""Agent Identity & Reputation Protocol — Ed25519 identities, reputation scoring, trust policies."""

from chainforge.enterprise.identity.identity import AgentIdentity
from chainforge.enterprise.identity.reputation import ReputationEngine, ReputationScore
from chainforge.enterprise.identity.trust import TrustPolicy, TrustRule, TrustDecision
from chainforge.enterprise.identity.credential import VerifiableCredential

__all__ = [
    "AgentIdentity",
    "ReputationEngine",
    "ReputationScore",
    "TrustPolicy",
    "TrustRule",
    "TrustDecision",
    "VerifiableCredential",
]
