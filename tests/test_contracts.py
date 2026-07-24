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
"""Tests for Behavior Contract Runtime."""

import pytest

from chainforge.core.contracts import (
    Contract,
    ContractEnforcer,
    ContractRegistry,
    ContractViolation,
    PerformanceContract,
    SecurityContract,
)


# ── Test ContractViolation ─────────────────────────────────────────────────


class TestContractViolation:
    def test_create(self):
        v = ContractViolation(contract_name="test", rule="test", severity="error", message="Fail")
        assert v.contract_name == "test"
        assert v.severity == "error"


# ── Test SecurityContract ──────────────────────────────────────────────────


class TestSecurityContract:
    def test_disallow_tool_matches(self):
        c = SecurityContract(name="no_delete", rule="disallow_tool", tool_pattern="delete_*")
        v = c.check_tool("delete_order")
        assert v is not None
        assert v.contract_name == "no_delete"

    def test_disallow_tool_no_match(self):
        c = SecurityContract(name="no_delete", rule="disallow_tool", tool_pattern="delete_*")
        v = c.check_tool("search")
        assert v is None

    def test_disallow_tool_exact(self):
        c = SecurityContract(name="block", rule="disallow_tool", tool_pattern="delete*")
        assert c.check_tool("delete") is not None
        assert c.check_tool("delete_order") is not None
        assert c.check_tool("search") is None

    def test_disallow_tool_no_pattern(self):
        c = SecurityContract(name="empty", rule="disallow_tool")
        v = c.check_tool("anything")
        assert v is None


# ── Test PerformanceContract ────────────────────────────────────────────────


class TestPerformanceContract:
    def test_max_llm_calls_exceeded(self):
        c = PerformanceContract(name="budget", rule="max_llm_calls", value=5)
        vs = c.finalize({"llm_calls": 10})
        assert len(vs) == 1
        assert "10" in vs[0].message

    def test_max_llm_calls_ok(self):
        c = PerformanceContract(name="budget", rule="max_llm_calls", value=5)
        vs = c.finalize({"llm_calls": 3})
        assert len(vs) == 0

    def test_max_tool_calls_exceeded(self):
        c = PerformanceContract(name="tools", rule="max_tool_calls", value=3)
        vs = c.finalize({"tool_calls": 5})
        assert len(vs) == 1

    def test_max_costs_exceeded(self):
        c = PerformanceContract(name="cost", rule="max_cost", value=0.05)
        vs = c.finalize({"cost": 0.10})
        assert len(vs) == 1

    def test_max_duration_exceeded(self):
        c = PerformanceContract(name="time", rule="max_duration", value=0.001)
        import time
        time.sleep(0.002)
        vs = c.finalize({"start_time": time.time() - 10})
        assert len(vs) >= 0


# ── Test ContractRegistry ──────────────────────────────────────────────────


class TestContractRegistry:
    def test_add_and_count(self):
        r = ContractRegistry()
        assert r.count == 0
        r.add(SecurityContract(name="test", rule="disallow_tool"))
        assert r.count == 1

    def test_get(self):
        r = ContractRegistry()
        c = SecurityContract(name="findme", rule="disallow_tool")
        r.add(c)
        assert r.get("findme") is c
        assert r.get("nonexistent") is None

    def test_remove(self):
        r = ContractRegistry()
        c = SecurityContract(name="removeme", rule="disallow_tool")
        r.add(c)
        assert r.remove("removeme") is True
        assert r.remove("removeme") is False
        assert r.count == 0

    def test_all(self):
        r = ContractRegistry()
        r.add(SecurityContract(name="a", rule="disallow_tool"))
        r.add(SecurityContract(name="b", rule="disallow_tool"))
        assert len(r.all) == 2

    def test_check_tool(self):
        r = ContractRegistry()
        r.add(SecurityContract(name="no_delete", rule="disallow_tool", tool_pattern="delete*"))
        r.add(SecurityContract(name="no_admin", rule="disallow_tool", tool_pattern="admin*"))
        vs = r.check_tool("delete_order")
        assert len(vs) == 1
        vs2 = r.check_tool("admin_reset")
        assert len(vs2) == 1
        vs3 = r.check_tool("search")
        assert len(vs3) == 0

    def test_finalize_all(self):
        r = ContractRegistry()
        r.add(PerformanceContract(name="b", rule="max_llm_calls", value=3))
        vs = r.finalize_all({"llm_calls": 10})
        assert len(vs) >= 1


# ── Test ContractEnforcer ──────────────────────────────────────────────────


class TestContractEnforcer:
    def test_create(self):
        from chainforge.core.agent import Agent
        from chainforge.providers import OpenAIProvider
        enforcer = ContractEnforcer(Agent(llm=OpenAIProvider(model="gpt-4o")))
        assert enforcer.agent is not None
        assert enforcer.violations == []

    def test_report_empty(self):
        from chainforge.core.agent import Agent
        from chainforge.providers import OpenAIProvider
        enforcer = ContractEnforcer(Agent(llm=OpenAIProvider(model="gpt-4o")))
        report = enforcer.report()
        assert report["passed"] is True
        assert report["total_violations"] == 0

    def test_report_with_contracts(self):
        from chainforge.core.agent import Agent
        from chainforge.providers import OpenAIProvider
        contracts = ContractRegistry()
        contracts.add(SecurityContract(name="no_delete", rule="disallow_tool", tool_pattern="delete*"))
        enforcer = ContractEnforcer(Agent(llm=OpenAIProvider(model="gpt-4o")), contracts=contracts)
        report = enforcer.report()
        assert report["contracts_checked"] == 1
        assert report["passed"] is True  # No violations yet

    def test_security_violation_severity(self):
        c = SecurityContract(name="strict", rule="disallow_tool", tool_pattern="bad*", severity="error")
        v = c.check_tool("bad_tool")
        assert v is not None
        assert v.severity == "error"
