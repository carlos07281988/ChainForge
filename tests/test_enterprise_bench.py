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
"""Tests for the Agent Benchmarking as Code module."""

import pytest

from chainforge.enterprise.bench.suite import BenchmarkExpectation, BenchmarkScenario
from chainforge.enterprise.bench.runner import BenchmarkResult
from chainforge.enterprise.bench.regression import RegressionDetector, RegressionReport


class TestBenchmarkExpectation:
    def test_default_values(self):
        exp = BenchmarkExpectation()
        assert exp.tool_calls_include == []
        assert exp.tool_calls_exclude == []
        assert exp.output_contains == []
        assert exp.output_not_contains == []
        assert exp.max_latency_ms is None
        assert exp.max_cost is None


class TestBenchmarkScenario:
    def test_model_creation(self):
        sc = BenchmarkScenario(
            name="refund_test",
            description="Test refund processing",
            input="I need a refund for order #123",
            expect=BenchmarkExpectation(
                tool_calls_include=["query_db", "send_email"],
                output_contains=["refund"],
            ),
            tags=["finance", "compliance"],
            weight=2.0,
        )
        assert sc.name == "refund_test"
        assert sc.tags == ["finance", "compliance"]
        assert sc.weight == 2.0
        assert sc.expect.tool_calls_include == ["query_db", "send_email"]


class TestBenchmarkResult:
    def test_checks_passed_failed(self):
        result = BenchmarkResult(
            scenario="refund",
            passed=False,
            checks_passed=["tool_called:query_db"],
            checks_failed=["tool_not_called:send_email"],
        )
        assert result.checks_passed == ["tool_called:query_db"]
        assert result.checks_failed == ["tool_not_called:send_email"]

    def test_passed_true_when_no_failures(self):
        result = BenchmarkResult(
            scenario="all_good",
            passed=True,
            checks_passed=["tool_called:query_db", "output_contains:refund"],
            checks_failed=[],
        )
        assert result.passed is True


class TestRegressionDetector:
    def test_detects_regressed_scenario(self):
        baseline = BenchmarkResult(
            scenario="refund", passed=True,
            checks_passed=["a", "b"], checks_failed=[]
        )
        candidate = BenchmarkResult(
            scenario="refund", passed=True,
            checks_passed=["a"], checks_failed=["b"]
        )
        detector = RegressionDetector(baseline=[baseline])
        report = detector.check([candidate])
        assert "refund" in report.regressed_scenarios

    def test_detects_improved_scenario(self):
        baseline = BenchmarkResult(
            scenario="refund", passed=True,
            checks_passed=["a"], checks_failed=["b"]
        )
        candidate = BenchmarkResult(
            scenario="refund", passed=True,
            checks_passed=["a", "b", "c"], checks_failed=[]
        )
        detector = RegressionDetector(baseline=[baseline])
        report = detector.check([candidate])
        assert "refund" in report.improved_scenarios


class TestRegressionReport:
    def test_summary_string(self):
        report = RegressionReport(
            regressed_scenarios=["bad_one"],
            improved_scenarios=["good_one", "better_one"],
            unchanged_scenarios=["same"],
            summary="1 regressed, 2 improved, 1 unchanged",
        )
        assert "regressed" in report.summary
        assert "improved" in report.summary
