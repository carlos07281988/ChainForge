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
"""Tests for the Collective Agent Memory module."""

import math
import time

import pytest

from chainforge.enterprise.collective.experience import Experience
from chainforge.enterprise.collective.forgetting import ForgettingCurve
from chainforge.enterprise.collective.memory import CollectiveMemory
from chainforge.enterprise.collective.resolver import ConflictResolver, ConflictResolution


class TestCollectiveMemory:
    def test_stores_and_retrieves_experiences(self):
        cm = CollectiveMemory(namespace="test-ns")
        exp = Experience(
            id="exp-1",
            task="refund order #123",
            task_type="refund",
            tools_used=["query_db", "send_email"],
            outcome="success",
            timestamp=time.time(),
        )
        cm.add(exp)
        assert cm.count == 1

        results = cm.search("refund order")
        assert len(results) == 1
        assert results[0].id == "exp-1"

    def test_search_returns_keyword_matches(self):
        cm = CollectiveMemory(namespace="test-ns")
        cm.add(Experience(id="1", task="process refund", task_type="refund",
                          outcome="success", timestamp=time.time()))
        cm.add(Experience(id="2", task="generate report", task_type="qa",
                          outcome="success", timestamp=time.time()))

        results = cm.search("refund")
        assert len(results) == 1
        assert results[0].id == "1"

    def test_search_respects_min_success_rate(self):
        cm = CollectiveMemory(namespace="test-ns")
        cm.add(Experience(id="1", task="fix bug in login", task_type="code_gen",
                          outcome="failure", timestamp=time.time()))
        cm.add(Experience(id="2", task="add new endpoint", task_type="code_gen",
                          outcome="success", timestamp=time.time()))

        results = cm.search("login", min_success_rate=0.5)
        assert len(results) == 0  # Only failure matches but filtered out


class TestForgettingCurve:
    def test_ebbinghaus_day_zero(self):
        assert ForgettingCurve.ebbinghaus(0.0) == 1.0

    def test_ebbinghaus_day_seven(self):
        val = ForgettingCurve.ebbinghaus(7.0, half_life=7.0)
        assert math.isclose(val, 0.5, rel_tol=0.01)

    def test_linear_reaches_zero_at_max_days(self):
        assert ForgettingCurve.linear(30.0, max_days=30.0) == 0.0
        assert ForgettingCurve.linear(0.0, max_days=30.0) == 1.0
        assert ForgettingCurve.linear(15.0, max_days=30.0) == 0.5

    def test_none_always_returns_one(self):
        assert ForgettingCurve.none(0.0) == 1.0
        assert ForgettingCurve.none(365.0) == 1.0


class TestExperience:
    def test_model_creation(self):
        exp = Experience(
            id="exp-42",
            task="handle customer complaint",
            task_type="support",
            tools_used=["search_kb", "send_email"],
            model_used="gpt-4o",
            outcome="success",
            feedback="Great resolution",
            cost=0.025,
            tokens=350,
            duration_ms=2300.0,
            timestamp=time.time(),
        )
        assert exp.id == "exp-42"
        assert exp.task_type == "support"
        assert exp.outcome == "success"
        assert len(exp.tools_used) == 2
        assert exp.decay_factor == 1.0


class TestConflictResolver:
    def test_detects_success_failure_contradictions(self):
        cm = CollectiveMemory(namespace="test-conflicts")
        cm.add(Experience(id="1", task="query database", task_type="db_query",
                          outcome="success", tools_used=["safe_query"],
                          timestamp=time.time()))
        cm.add(Experience(id="2", task="query database badly", task_type="db_query",
                          outcome="failure", tools_used=["raw_sql"],
                          timestamp=time.time()))
        cm.add(Experience(id="3", task="another success", task_type="db_query",
                          outcome="success", tools_used=["safe_query"],
                          timestamp=time.time()))

        resolver = ConflictResolver(memory=cm)
        conflicts = resolver.find_conflicts()
        assert len(conflicts) == 1
        assert conflicts[0].task_type == "db_query"
        assert "success" in conflicts[0].agent_a_outcome
        assert "failure" in conflicts[0].agent_b_outcome
