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
"""Governance 2.0 — policy-driven security, residency, and audit for agents.

Provides:
  - GovernancePolicy + PolicyEngine: declarative rule evaluation
  - DataResidency: data-locality enforcement (PII → local models)
  - ModelVersionTracker: model version pinning for reproducibility
  - AuditReporter: compliance audit reports from provenance + tracing data

Usage:
    from chainforge.governance import PolicyEngine, GovernancePolicy
    from chainforge.governance.residency import DataResidency

    engine = PolicyEngine(policies=[
        GovernancePolicy(name="pii-local", data_labels=["pii"],
                         model_provider="nim", action="enforce"),
    ])

    decision = await engine.evaluate(["pii"], context={})
    # → PolicyDecision(allowed_providers=["nim"], blocked=False)
"""

from chainforge.governance.policy import (
    GovernancePolicy,
    PolicyDecision,
    PolicyEngine,
)
from chainforge.governance.residency import DataResidency
from chainforge.governance.versioning import ModelVersionTracker, VersionRecord
from chainforge.governance.audit import AuditReporter, AuditReport, ComplianceItem

__all__ = [
    "GovernancePolicy",
    "PolicyDecision",
    "PolicyEngine",
    "DataResidency",
    "ModelVersionTracker",
    "VersionRecord",
    "AuditReporter",
    "AuditReport",
    "ComplianceItem",
]
