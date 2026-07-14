"""Tests for the Agent Inspector."""

import pytest
from chainforge.inspector import inspector, AgentInspector, InspectionEvent


class TestInspectionEvent:
    def test_defaults(self):
        e = InspectionEvent(agent_id="test", type="state", state="idle")
        assert e.agent_id == "test"
        assert e.type == "state"
        assert e.state == "idle"
        assert e.iteration == 0
        assert e.id is not None
        assert e.timestamp is not None

    def test_content_and_data(self):
        e = InspectionEvent(agent_id="a1", type="tool_call", state="executing_tool", content="Calculating", data={"tool": "calc"})
        assert e.content == "Calculating"
        assert e.data["tool"] == "calc"


class TestAgentInspector:
    def setup_method(self):
        self.ins = AgentInspector()

    def test_start_and_end_run(self):
        self.ins.start_run("agent-1")
        summary = self.ins.get_summary("agent-1")
        assert summary is not None
        assert summary["agent_id"] == "agent-1"

        self.ins.end_run("agent-1")
        summary = self.ins.get_summary("agent-1")
        assert summary["end_time"] is not None

    def test_record_event(self):
        self.ins.start_run("agent-1")
        event = self.ins.record_event("agent-1", "state", state="thinking", iteration=1)
        assert event is not None
        assert event.type == "state"
        assert event.state == "thinking"
        assert event.iteration == 1

    def test_record_event_no_run(self):
        event = self.ins.record_event("nonexistent", "state")
        assert event is None

    def test_get_events(self):
        self.ins.start_run("agent-1")
        self.ins.record_event("agent-1", "state", state="thinking", iteration=1)
        self.ins.record_event("agent-1", "tool_call", state="executing_tool", content="calc", iteration=2)
        self.ins.record_event("agent-1", "text", state="responding", content="Answer: 42", iteration=3)

        events = self.ins.get_events("agent-1")
        assert len(events) == 3  # Newest first

    def test_get_events_filtered(self):
        self.ins.start_run("agent-1")
        self.ins.record_event("agent-1", "state")
        self.ins.record_event("agent-1", "tool_call")
        self.ins.record_event("agent-1", "text")

        tool_events = self.ins.get_events("agent-1", event_type="tool_call")
        assert len(tool_events) == 1
        assert tool_events[0].type == "tool_call"

    def test_get_summary(self):
        self.ins.start_run("agent-1")
        self.ins.record_event("agent-1", "state", state="thinking", iteration=1)
        self.ins.record_event("agent-1", "tool_call", state="executing_tool", iteration=2)
        self.ins.record_event("agent-1", "state", state="thinking", iteration=3)
        self.ins.end_run("agent-1")

        summary = self.ins.get_summary("agent-1")
        assert summary["tool_calls"] == 1
        assert summary["iterations"] >= 3

    def test_get_summary_no_agent(self):
        summary = self.ins.get_summary("nonexistent")
        assert summary is None

    def test_list_agents(self):
        self.ins.start_run("agent-1")
        self.ins.start_run("agent-2")
        agents = self.ins.list_agents()
        assert len(agents) >= 2

    def test_clear_specific(self):
        self.ins.start_run("agent-1")
        self.ins.start_run("agent-2")
        self.ins.clear("agent-1")
        assert self.ins.get_summary("agent-1") is None
        assert self.ins.get_summary("agent-2") is not None

    def test_clear_all(self):
        self.ins.start_run("agent-1")
        self.ins.start_run("agent-2")
        self.ins.clear()
        assert self.ins.get_summary("agent-1") is None
        assert self.ins.get_summary("agent-2") is None

    def test_counters(self):
        self.ins.start_run("agent-1")
        for i in range(5):
            self.ins.record_event("agent-1", "tool_call")
        summary = self.ins.get_summary("agent-1")
        assert summary["tool_calls"] == 5

    def test_error_counter(self):
        self.ins.start_run("agent-1")
        self.ins.record_event("agent-1", "state")
        self.ins.record_event("agent-1", "error", content="Something went wrong")
        self.ins.end_run("agent-1")
        summary = self.ins.get_summary("agent-1")
        assert summary["errors"] == 1


class TestGlobalInspector:
    def test_global_singleton(self):
        from chainforge.inspector import inspector as ins1
        from chainforge.inspector.inspector import inspector as ins2
        assert ins1 is ins2
