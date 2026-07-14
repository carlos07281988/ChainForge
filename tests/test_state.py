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
"""Tests for agent state machine."""

import time

from chainforge.core.state import AgentState, StateTracker, StateTransition


class TestAgentState:
    def test_enum_values(self):
        assert AgentState.initializing.value == "initializing"
        assert AgentState.thinking.value == "thinking"
        assert AgentState.executing_tool.value == "executing_tool"
        assert AgentState.observing.value == "observing"
        assert AgentState.responding.value == "responding"
        assert AgentState.error.value == "error"
        assert AgentState.done.value == "done"


class TestStateTransition:
    def test_transition_defaults(self):
        t = StateTransition(to_state=AgentState.thinking)
        assert t.to_state == AgentState.thinking
        assert t.from_state is None
        assert t.iteration == 0
        assert t.depth == 0
        assert t.tool_name is None

    def test_transition_with_metadata(self):
        t = StateTransition(
            from_state=AgentState.thinking,
            to_state=AgentState.executing_tool,
            iteration=2,
            depth=1,
            tool_name="search",
            message="Searching...",
        )
        assert t.from_state == AgentState.thinking
        assert t.to_state == AgentState.executing_tool
        assert t.iteration == 2
        assert t.tool_name == "search"


class TestStateTracker:
    def test_initial_state(self):
        tracker = StateTracker()
        assert tracker.current_state == AgentState.initializing
        assert tracker.iteration == 0
        assert tracker.depth == 0

    def test_simple_transition(self):
        tracker = StateTracker()
        t = tracker.transition(AgentState.thinking, iteration=0)
        assert tracker.current_state == AgentState.thinking
        assert t.to_state == AgentState.thinking
        assert len(tracker.history) == 1

    def test_multiple_transitions(self):
        tracker = StateTracker()
        tracker.transition(AgentState.thinking, iteration=0)
        tracker.transition(AgentState.executing_tool, tool_name="search", iteration=0)
        tracker.transition(AgentState.observing, iteration=0)
        assert len(tracker.history) == 3
        assert tracker.current_state == AgentState.observing

    def test_listener_notified(self):
        tracker = StateTracker()
        received = []

        def listener(t):
            received.append(t.to_state)

        tracker.on_transition(listener)
        tracker.transition(AgentState.thinking, iteration=0)
        tracker.transition(AgentState.executing_tool, iteration=0)
        assert len(received) == 2
        assert received[0] == AgentState.thinking

    def test_unregister_listener(self):
        tracker = StateTracker()
        received = []

        def listener(t):
            received.append(t.to_state)

        unregister = tracker.on_transition(listener)
        tracker.transition(AgentState.thinking, iteration=0)
        unregister()
        tracker.transition(AgentState.done, iteration=1)
        assert len(received) == 1

    def test_reset(self):
        tracker = StateTracker()
        tracker.transition(AgentState.thinking, iteration=0)
        tracker.transition(AgentState.executing_tool, iteration=0)
        tracker.reset()
        assert tracker.current_state == AgentState.initializing
        assert tracker.iteration == 0
        assert tracker.history == []

    def test_to_stream_events(self):
        tracker = StateTracker()
        tracker.transition(AgentState.thinking, iteration=0)
        tracker.transition(AgentState.executing_tool, tool_name="search", iteration=0)
        events = tracker.to_stream_events()
        assert len(events) == 2
        assert events[0].data["state"] == "thinking"
        assert events[1].data["state"] == "executing_tool"
        assert events[1].data["tool_name"] == "search"

    def test_iteration_tracking(self):
        tracker = StateTracker()
        tracker.transition(AgentState.thinking, iteration=0)
        assert tracker.iteration == 0
        tracker.transition(AgentState.executing_tool, iteration=0)
        assert tracker.iteration == 0
        tracker.transition(AgentState.observing, iteration=0)
        assert tracker.iteration == 0
        # New iteration
        tracker.transition(AgentState.thinking, iteration=1)
        assert tracker.iteration == 1

    def test_depth_tracking(self):
        tracker = StateTracker()
        tracker.transition(AgentState.thinking, depth=0)
        assert tracker.depth == 0
        tracker.transition(AgentState.thinking, depth=1)
        assert tracker.depth == 1
