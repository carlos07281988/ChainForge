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
"""Tests for the Agent Identity & Reputation module."""

import time
from unittest import mock

import pytest

from chainforge.enterprise.identity.identity import AgentIdentity
from chainforge.enterprise.identity.reputation import ReputationEngine, ReputationScore
from chainforge.enterprise.identity.trust import TrustPolicy, TrustRule
from chainforge.enterprise.identity.credential import VerifiableCredential


class TestAgentIdentity:
    def test_create_generates_valid_fields(self):
        ident = AgentIdentity.create(name="test-agent", organization="acme")
        assert ident.agent_id.startswith("cf-")
        assert ident.name == "test-agent"
        assert ident.organization == "acme"
        assert len(ident.public_key) > 0
        assert ident.did.startswith("did:chainforge:")

    def test_sign_verify_round_trip(self):
        ident = AgentIdentity.create(name="agent-a")
        payload = b"hello world"
        sig = ident.sign(payload)
        assert len(sig) > 0
        assert AgentIdentity.verify(payload, sig, ident.public_key) is True

    def test_verify_tampered_data(self):
        ident = AgentIdentity.create(name="agent-b")
        payload = b"original data"
        sig = ident.sign(payload)
        assert AgentIdentity.verify(b"tampered data", sig, ident.public_key) is False

    def test_to_json_excludes_private_key(self):
        ident = AgentIdentity.create(name="agent-c")
        data = ident.to_json()
        assert "_private_key" not in data
        assert "agent_id" in data
        assert "public_key" in data
        assert "did" in data


class TestReputationEngine:
    def test_records_events_and_produces_scores(self):
        engine = ReputationEngine()
        engine.record_event("agent-1", "successful_call", latency_ms=200)
        engine.record_event("agent-2", "accurate_tool_choice")
        engine.record_event("agent-2", "successful_call", latency_ms=300)

        score1 = engine.score("agent-1")
        assert score1.agent_id == "agent-1"
        assert 0 <= score1.overall <= 100

        score2 = engine.score("agent-2")
        assert 0 <= score2.overall <= 100

    def test_score_decreases_after_security_incident(self):
        engine = ReputationEngine()
        engine.record_event("agent-x", "successful_call", latency_ms=100)
        score_before = engine.score("agent-x")
        engine.record_event("agent-x", "data_exfiltration")
        score_after = engine.score("agent-x")
        assert score_after.safety < score_before.safety


class TestTrustPolicy:
    def test_allowed_with_high_reputation(self):
        policy = TrustPolicy(rules=[
            TrustRule(min_reputation=50.0, action="allow", reason="Good reputation"),
            TrustRule(max_reputation=49.0, action="block_all_tools", reason="Low rep"),
        ])
        score = ReputationScore(agent_id="a1", overall=75.0)
        decision = policy.evaluate(score)
        assert decision.allowed is True
        assert decision.action == "allow"

    def test_blocked_with_low_reputation(self):
        policy = TrustPolicy(rules=[
            TrustRule(max_reputation=49.0, action="block_all_tools", reason="Low rep"),
            TrustRule(min_reputation=50.0, action="allow", reason="Good reputation"),
        ])
        score = ReputationScore(agent_id="a2", overall=30.0)
        decision = policy.evaluate(score)
        assert decision.allowed is False
        assert decision.action == "block_all_tools"


class TestVerifiableCredential:
    def test_issue_verify_round_trip(self):
        issuer = AgentIdentity.create(name="issuer-org")
        cred = VerifiableCredential.issue(
            issuer=issuer,
            subject_id="subject-001",
            claims={"role": "admin", "level": 3},
        )
        assert cred.issuer_id == issuer.agent_id
        assert cred.subject_id == "subject-001"
        assert len(cred.signature) > 0
        assert cred.verify(issuer.public_key) is True

    def test_rejects_expired_credential(self):
        issuer = AgentIdentity.create(name="issuer-org")
        cred = VerifiableCredential.issue(
            issuer=issuer,
            subject_id="subject-002",
            claims={"role": "viewer"},
            expires_in_days=180,
        )
        # Override expires_at to simulate an expired credential
        cred.expires_at = time.time() - 1
        assert cred.verify(issuer.public_key) is False
