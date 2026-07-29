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
"""Tests for the EU AI Act Compliance module."""

import json
import tempfile
from pathlib import Path

import pytest

from chainforge.enterprise.compliance.classifier import RiskClassifier, RiskRule, RiskTier
from chainforge.enterprise.compliance.hitl import HITLPolicy, ApprovalRequest
from chainforge.enterprise.compliance.auditor import ComplianceAuditor, ComplianceReport, ComplianceCheck


class TestRiskClassifier:
    def test_delete_tools_return_high(self):
        classifier = RiskClassifier()
        tier, rules = classifier.classify(tools=["delete_file", "query_db"])
        assert tier == RiskTier.HIGH
        assert any("delete" in r.reason for r in rules)

    def test_healthcare_domain_returns_high(self):
        classifier = RiskClassifier()
        tier, rules = classifier.classify(tools=["query_db"], domain="healthcare")
        assert tier == RiskTier.HIGH
        assert any("healthcare" in r.reason.lower() for r in rules)

    def test_pii_cloud_returns_high(self):
        classifier = RiskClassifier()
        tier, rules = classifier.classify(
            tools=["summarize_text"], data_labels=["pii"]
        )
        assert tier == RiskTier.HIGH
        assert any("PII" in r.reason for r in rules)

    def test_safe_tools_return_minimal(self):
        classifier = RiskClassifier()
        tier, rules = classifier.classify(tools=["greet_user", "summarize_text"])
        assert tier == RiskTier.MINIMAL
        assert rules == []

    def test_send_email_returns_limited(self):
        classifier = RiskClassifier()
        tier, rules = classifier.classify(tools=["send_email"])
        assert tier == RiskTier.LIMITED


class TestHITLPolicy:
    def test_needs_approval_for_configured_tiers(self):
        policy = HITLPolicy(require_approval_on=[RiskTier.HIGH])
        assert policy.needs_approval(RiskTier.HIGH) is True
        assert policy.needs_approval(RiskTier.MINIMAL) is False

    def test_needs_approval_empty_list(self):
        policy = HITLPolicy(require_approval_on=[])
        assert policy.needs_approval(RiskTier.HIGH) is False


class TestComplianceAuditor:
    def test_generates_report_with_articles_11_15(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "test_compliance.db")
            auditor = ComplianceAuditor(log_path=db_path)
            auditor.record("risk_classification", {"risk_tier": "high"})
            report = auditor.generate(risk_tier="high", has_hitl=True)
            auditor.close()

            article_numbers = {c.article for c in report.checks}
            assert 11 in article_numbers
            assert 12 in article_numbers
            assert 13 in article_numbers
            assert 14 in article_numbers
            assert 15 in article_numbers

    def test_generates_markdown_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "test_compliance.db")
            auditor = ComplianceAuditor(log_path=db_path)
            auditor.record("risk_classification", {"risk_tier": "limited"})
            report = auditor.generate(risk_tier="limited", has_hitl=True)
            auditor.close()

            md = report.to_markdown()
            assert md.startswith("# Compliance Report:") is True
            assert "## Article Checks" in md

    def test_to_json_exports_properly(self):
        report = ComplianceReport(
            risk_tier="minimal",
            checks=[
                ComplianceCheck(article=11, requirement="Tech docs", status="compliant"),
            ],
            total_events=3,
        )
        data = report.to_json()
        assert data["risk_tier"] == "minimal"
        assert data["total_events"] == 3
        assert len(data["checks"]) == 1

    def test_compliance_score_calculation(self):
        report = ComplianceReport(
            checks=[
                ComplianceCheck(article=11, requirement="A", status="compliant"),
                ComplianceCheck(article=12, requirement="B", status="compliant"),
                ComplianceCheck(article=13, requirement="C", status="non_compliant"),
                ComplianceCheck(article=14, requirement="D", status="compliant"),
            ]
        )
        assert report.compliance_score == 0.75

    def test_compliance_score_empty_checks(self):
        report = ComplianceReport(checks=[])
        assert report.compliance_score == 1.0


class TestApprovalRequest:
    def test_model_creation(self):
        req = ApprovalRequest(
            request_id="req-001",
            agent_name="test-agent",
            action="delete_file",
            risk_tier=RiskTier.HIGH,
            reason="Risky operation",
        )
        assert req.request_id == "req-001"
        assert req.agent_name == "test-agent"
        assert req.risk_tier == RiskTier.HIGH
        assert req.reason == "Risky operation"
