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
"""Tests for the Agent Economics module."""

import time

import pytest

from chainforge.enterprise.economics.ledger import CostRecord, TokenLedger
from chainforge.enterprise.economics.tracker import CostTracker
from chainforge.enterprise.economics.report import CostReport, CostOptimization
from chainforge.enterprise.economics.guard import BudgetGuard


class TestCostTracker:
    def test_creates_with_memory_backend(self):
        tracker = CostTracker(backend="memory")
        assert tracker._ledger is not None
        assert tracker._ledger._backend == "memory"


class TestCostRecord:
    def test_correctly_stores_data(self):
        record = CostRecord(
            model="gpt-4o",
            provider="openai",
            input_tokens=100,
            output_tokens=50,
            cost=0.015,
            duration_ms=1200.0,
            attribution={"project": "test"},
        )
        assert record.model == "gpt-4o"
        assert record.provider == "openai"
        assert record.input_tokens == 100
        assert record.output_tokens == 50
        assert record.cost == 0.015
        assert record.duration_ms == 1200.0
        assert record.attribution["project"] == "test"

    def test_auto_assigns_timestamp(self):
        before = time.time()
        record = CostRecord(model="test")
        after = time.time()
        assert before <= record.timestamp <= after


class TestTokenLedger:
    def test_records_and_queries(self):
        ledger = TokenLedger(backend="memory")
        r1 = CostRecord(model="gpt-4o", cost=0.05, input_tokens=100)
        r2 = CostRecord(model="gpt-4o-mini", cost=0.01, input_tokens=50)
        ledger.record(r1)
        ledger.record(r2)

        results = ledger.query(group_by="model")
        assert len(results) >= 2
        models = {r["dimension"] for r in results}
        assert "gpt-4o" in models
        assert "gpt-4o-mini" in models

    def test_query_with_group_by_returns_aggregated(self):
        ledger = TokenLedger(backend="memory")
        r1 = CostRecord(model="gpt-4o", cost=0.10, input_tokens=200, output_tokens=100)
        r2 = CostRecord(model="gpt-4o", cost=0.05, input_tokens=100, output_tokens=50)
        r3 = CostRecord(model="claude-sonnet-4", cost=0.03, input_tokens=80, output_tokens=40)
        ledger.record(r1)
        ledger.record(r2)
        ledger.record(r3)

        results = ledger.query(group_by="model")
        gpt_row = next(r for r in results if r["dimension"] == "gpt-4o")
        assert gpt_row["calls"] == 2
        assert gpt_row["total_cost"] == pytest.approx(0.15)
        assert gpt_row["total_input_tokens"] == 300
        assert gpt_row["total_output_tokens"] == 150


class TestCostReport:
    def test_serialization(self):
        report = CostReport(
            total=10.50,
            rows=[
                {"dimension": "gpt-4o", "calls": 3, "total_input_tokens": 500,
                 "total_output_tokens": 200, "total_cost": 7.50},
            ],
            group_by="model",
            period="today",
        )
        data = report.to_json()
        assert len(data) == 1
        assert data[0]["dimension"] == "gpt-4o"


class TestCostOptimization:
    def test_model_creation(self):
        opt = CostOptimization(
            potential_savings=125.50,
            items=["Switch gpt-4o -> gpt-4o-mini: save ~$125.50"],
        )
        assert opt.potential_savings == 125.50
        assert len(opt.items) == 1


class TestBudgetGuard:
    def test_default_properties(self):
        guard = BudgetGuard()
        assert guard._daily_limit == 50.0
        assert guard._on_limit == "downgrade"
        assert guard._fallback_model is None

    def test_custom_config(self):
        guard = BudgetGuard(
            daily_limit=100.0,
            on_limit="block",
            fallback_model="gpt-4o-mini",
        )
        assert guard.daily_limit == 100.0
        assert guard._on_limit == "block"
        assert guard._fallback_model == "gpt-4o-mini"
