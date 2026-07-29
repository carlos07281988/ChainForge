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
"""Tests for the Agent Data Lineage & GDPR module."""

import pytest

from chainforge.enterprise.lineage.query import DataSubject, DataLocation, DataFootprint
from chainforge.enterprise.lineage.tracker import DataLineageTracker
from chainforge.enterprise.lineage.erasure import ErasureRequest, ErasureReport, ErasureItem
from chainforge.enterprise.lineage.proof import DeletionProof


class TestDataSubject:
    def test_creation_with_email_and_user_id(self):
        subject = DataSubject(email="user@example.com", user_id="usr-001")
        assert subject.email == "user@example.com"
        assert subject.user_id == "usr-001"


class TestDataLineageTracker:
    def test_records_locations_and_queries_footprint(self):
        tracker = DataLineageTracker(backend="memory")
        subject = DataSubject(email="alice@acme.com")
        loc = DataLocation(
            type="llm_response",
            provider="openai",
            identifier="chat-cmpl-abc123",
            content_type="pii",
        )
        tracker.record_location(subject, loc)
        footprint = tracker.query(subject)
        assert footprint.total_locations == 1
        assert footprint.locations[0].type == "llm_response"

    def test_empty_tracker_returns_empty_footprint(self):
        tracker = DataLineageTracker(backend="memory")
        subject = DataSubject(email="noone@void.com")
        footprint = tracker.query(subject)
        assert footprint.total_locations == 0
        assert footprint.locations == []

    def test_risk_assessment_thresholds(self):
        tracker = DataLineageTracker(backend="memory")
        subject = DataSubject(email="heavy@acme.com")

        # Add 6 locations -> medium risk
        for i in range(6):
            tracker.record_location(subject,
                DataLocation(type=f"type_{i}", provider="test",
                             identifier=f"id_{i}"))
        footprint = tracker.query(subject)
        assert footprint.risk_assessment == "medium"

        # Add up to > 20 -> high risk
        tracker2 = DataLineageTracker(backend="memory")
        for i in range(21):
            tracker2.record_location(subject,
                DataLocation(type=f"type_{i}", provider="test",
                             identifier=f"id_{i}", content_type="pii"))
        fp2 = tracker2.query(subject)
        assert fp2.risk_assessment == "high"

    def test_register_handler_stores_handler(self):
        tracker = DataLineageTracker(backend="memory")

        async def custom_handler(loc):
            pass

        tracker.register_handler("custom_type", custom_handler)
        assert "custom_type" in tracker._handlers


class TestErasureRequest:
    def test_model_creation(self):
        req = ErasureRequest(
            data_subjects=[{"email": "user@example.com"}],
            reason="GDPR Article 17",
            requested_by="dpo@acme.com",
        )
        assert len(req.request_id) == 12
        assert req.data_subjects[0]["email"] == "user@example.com"
        assert req.reason == "GDPR Article 17"


class TestErasureReport:
    def test_completion_rate_calculation(self):
        report = ErasureReport(
            total_items=4,
            completed_items=3,
            pending_items=1,
            status="partial",
        )
        assert report.completion_rate == 0.75

    def test_completion_rate_zero_items(self):
        report = ErasureReport(total_items=0)
        assert report.completion_rate == 1.0


class TestDeletionProof:
    def test_verify_true_for_consistent_report(self):
        report = ErasureReport(
            request_id="req-abc",
            status="complete",
            completed_items=5,
            total_items=5,
        )
        proof = DeletionProof(report)
        assert proof.verify() is True
        assert len(proof.proof_hash) == 64  # sha256 hex digest
