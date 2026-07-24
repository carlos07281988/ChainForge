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
"""Tests for Execution Provenance Graph."""

import asyncio

import pytest

from chainforge.core.message import Message
from chainforge.core.provenance import ProvenanceNode, ProvenanceTracker, ProvenanceStore
from chainforge.core.stream import EventType, StreamEvent


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_event(etype: str, content: str = "", data: dict | None = None,
                timestamp: float | None = None) -> StreamEvent:
    return StreamEvent(type=EventType(etype), content=content, data=data or {})


async def _dummy_stream(events: list[tuple[str, str, dict | None]]) -> list[StreamEvent]:
    """Yield StreamEvents from a list of (type, content, data) tuples."""
    result = []
    for etype, content, data in events:
        ev = _make_event(etype, content, data)
        result.append(ev)
        yield ev
    yield StreamEvent(type=EventType.done)


# ── Test ProvenanceNode ───────────────────────────────────────────────────


class TestProvenanceNode:
    def test_create_node(self):
        node = ProvenanceNode(id="n1", node_type="tool_call", data={"name": "search"})
        assert node.id == "n1"
        assert node.node_type == "tool_call"
        assert node.data["name"] == "search"
        assert node.caused_by is None
        assert node.causal_group == "0"

    def test_node_with_caused_by(self):
        node = ProvenanceNode(id="n2", node_type="tool_result", caused_by="n1")
        assert node.caused_by == "n1"

    def test_path_label_tool_call(self):
        node = ProvenanceNode(id="n1", node_type="tool_call",
                              data={"name": "search", "args": {"q": "test"}})
        label = node.path_label()
        assert "search" in label
        assert "test" in label

    def test_path_label_user_input(self):
        node = ProvenanceNode(id="n1", node_type="user_input",
                              data={"content": "hello world"})
        assert "hello" in node.path_label()

    def test_path_label_llm_response(self):
        node = ProvenanceNode(id="n1", node_type="llm_response",
                              data={"content": "Hi there!"})
        assert "Hi" in node.path_label()

    def test_path_label_error(self):
        node = ProvenanceNode(id="n1", node_type="error",
                              data={"message": "Something broke"})
        assert "Something" in node.path_label()

    def test_path_label_tool_result(self):
        node = ProvenanceNode(id="n1", node_type="tool_result",
                              data={"content": "42 degrees", "is_error": False})
        assert "42" in node.path_label()

    def test_repr(self):
        node = ProvenanceNode(id="test_id_12345", node_type="tool_call")
        r = repr(node)
        assert "ProvNode" in r
        assert "tool_call" in r


# ── Test ProvenanceTracker ─────────────────────────────────────────────────


class TestProvenanceTracker:
    def test_create_tracker(self):
        tracker = ProvenanceTracker()
        assert tracker.session_id is not None
        assert tracker.node_count == 0
        assert tracker.nodes == []

    def test_record_and_track(self):
        tracker = ProvenanceTracker()

        async def _track():
            stream = _dummy_stream([
                ("text", "Hello", None),
                ("text", "World", None),
            ])
            async for _ in tracker.track(stream, user_prompt="test input"):
                pass
            return tracker

        t = asyncio.run(_track())
        assert t.node_count >= 3  # user_input + 2 text events + state
        assert any(n.node_type == "user_input" for n in t.nodes)
        assert any(n.node_type == "llm_response" for n in t.nodes)

    def test_tool_call_provenance(self):
        tracker = ProvenanceTracker()

        async def _track():
            stream = _dummy_stream([
                ("text", "Let me search", None),
                ("tool_call", "", {"name": "search", "args": {"q": "weather"}}),
                ("tool_result", "", {"name": "search", "content": "sunny", "is_error": False}),
                ("text", "It's sunny", None),
            ])
            async for _ in tracker.track(stream, user_prompt="weather?"):
                pass
            return tracker

        t = asyncio.run(_track())
        assert len(t.tool_calls()) == 1
        assert len(t.by_type("tool_result")) == 1
        assert len(t.by_type("llm_response")) >= 1

    def test_error_tracking(self):
        tracker = ProvenanceTracker()

        async def _track():
            stream = _dummy_stream([
                ("text", "Hello", None),
                ("error", "Something broke", None),
            ])
            async for _ in tracker.track(stream, user_prompt="test"):
                pass
            return tracker

        t = asyncio.run(_track())
        assert len(t.errors()) == 1

    def test_trace_decision(self):
        tracker = ProvenanceTracker()

        async def _track():
            stream = _dummy_stream([
                ("text", "Hello", None),
                ("tool_call", "", {"name": "search", "args": {"q": "x"}}),
                ("tool_result", "", {"name": "search", "content": "result"}),
            ])
            async for _ in tracker.track(stream, user_prompt="test"):
                pass
            return tracker

        t = asyncio.run(_track())
        # Find the last node and trace it
        last_id = list(t._nodes.keys())[-1]
        chain = t.trace_decision(last_id)
        assert len(chain) >= 4  # input → response → tool_call → tool_result → state

        # Root should be user_input
        assert chain[0].node_type == "user_input"

    def test_graph_output(self):
        tracker = ProvenanceTracker()

        async def _track():
            stream = _dummy_stream([
                ("text", "Hi", None),
                ("tool_call", "", {"name": "search", "args": {}}),
            ])
            async for _ in tracker.track(stream, user_prompt="hello"):
                pass
            return tracker

        t = asyncio.run(_track())
        g = t.graph()
        assert "nodes" in g
        assert "edges" in g
        assert g["node_count"] == len(g["nodes"])
        assert g["edge_count"] == len(g["edges"])
        assert g["node_count"] >= 3

    def test_critical_path(self):
        tracker = ProvenanceTracker()

        async def _track():
            stream = _dummy_stream([
                ("text", "Thinking", None),
                ("tool_call", "", {"name": "calc", "args": {"expr": "2+2"}}),
                ("tool_result", "", {"name": "calc", "content": "4"}),
                ("text", "Answer is 4", None),
            ])
            async for _ in tracker.track(stream, user_prompt="calc"):
                pass
            return tracker

        t = asyncio.run(_track())
        cp = t.critical_path()
        assert len(cp) >= 2  # At least user_input + some decision nodes

    def test_path(self):
        tracker = ProvenanceTracker()

        async def _track():
            stream = _dummy_stream([
                ("text", "One", None),
                ("text", "Two", None),
            ])
            async for _ in tracker.track(stream, user_prompt="test"):
                pass
            return tracker

        t = asyncio.run(_track())
        path = t.path()
        assert len(path) >= 2
        assert path[0].node_type == "user_input"

    def test_summary(self):
        tracker = ProvenanceTracker()

        async def _track():
            stream = _dummy_stream([
                ("text", "Hello", None),
                ("tool_call", "", {"name": "s", "args": {}}),
            ])
            async for _ in tracker.track(stream, user_prompt="hi"):
                pass
            return tracker

        t = asyncio.run(_track())
        s = t.summary()
        assert s["nodes"] > 0
        assert "by_type" in s
        assert "tool_calls" in s
        assert "errors" in s

    def test_format_chain(self):
        tracker = ProvenanceTracker()

        async def _track():
            stream = _dummy_stream([("text", "Hello", None)])
            async for _ in tracker.track(stream, user_prompt="test"):
                pass
            return tracker

        t = asyncio.run(_track())
        formatted = t.format_chain()
        assert "user_input" in formatted
        assert "llm_response" in formatted

    def test_session_id(self):
        tracker = ProvenanceTracker(session_id="my-session")
        assert tracker.session_id == "my-session"

    def test_node_count(self):
        tracker = ProvenanceTracker()
        assert tracker.node_count == 0

    def test_errors_empty(self):
        tracker = ProvenanceTracker()
        assert tracker.errors() == []

    def test_tool_calls_empty(self):
        tracker = ProvenanceTracker()
        assert tracker.tool_calls() == []

    def test_by_type_empty(self):
        tracker = ProvenanceTracker()
        assert tracker.by_type("llm_call") == []

    def test_path_empty(self):
        tracker = ProvenanceTracker()
        assert tracker.path() == []

    def test_graph_empty(self):
        tracker = ProvenanceTracker()
        g = tracker.graph()
        assert g["node_count"] == 0
        assert g["edge_count"] == 0

    def test_critical_path_empty(self):
        tracker = ProvenanceTracker()
        assert tracker.critical_path() == []

    def test_trace_decision_not_found(self):
        tracker = ProvenanceTracker()
        chain = tracker.trace_decision("nonexistent")
        assert chain == []


# ── Test ProvenanceStore ───────────────────────────────────────────────────


class TestProvenanceStore:
    def test_save_and_load(self):
        store = ProvenanceStore(":memory:")
        node = ProvenanceNode(id="n1", node_type="test", data={"key": "val"})
        store.save_node("session-1", node)
        loaded = store.load_node("session-1", "n1")
        assert loaded is not None
        assert loaded.id == "n1"
        assert loaded.node_type == "test"
        assert loaded.data["key"] == "val"

    def test_load_session(self):
        store = ProvenanceStore(":memory:")
        for i in range(3):
            store.save_node("s1", ProvenanceNode(id=f"n{i}", node_type="test"))
        nodes = store.load_session("s1")
        assert len(nodes) == 3

    def test_load_session_graph(self):
        store = ProvenanceStore(":memory:")
        n1 = ProvenanceNode(id="n1", node_type="user_input", data={"content": "hi"})
        n2 = ProvenanceNode(id="n2", node_type="llm_response", caused_by="n1")
        store.save_node("s1", n1)
        store.save_node("s1", n2)
        g = store.load_session_graph("s1")
        assert g["node_count"] == 2
        assert g["edge_count"] == 1

    def test_list_sessions(self):
        store = ProvenanceStore(":memory:")
        store.save_node("s1", ProvenanceNode(id="n1", node_type="test"))
        store.save_node("s2", ProvenanceNode(id="n2", node_type="test"))
        sessions = store.list_sessions()
        assert len(sessions) >= 2

    def test_load_node_not_found(self):
        store = ProvenanceStore(":memory:")
        assert store.load_node("nonexistent", "nope") is None


# ── Test Integration ───────────────────────────────────────────────────────


class TestProvenanceIntegration:
    def test_tracker_with_store(self):
        store = ProvenanceStore(":memory:")
        tracker = ProvenanceTracker(store=store)

        async def _run():
            stream = _dummy_stream([("text", "Hello", None)])
            async for _ in tracker.track(stream, user_prompt="test"):
                pass
            return tracker

        asyncio.run(_run())
        assert tracker.node_count > 0

        # Nodes should be persisted to store
        nodes = store.load_session(tracker.session_id)
        assert len(nodes) >= 2

    def test_causal_chain_structure(self):
        """Verify the causal chain has the right order and connections."""
        tracker = ProvenanceTracker()

        async def _run():
            stream = _dummy_stream([
                ("text", "Let me search", None),
                ("tool_call", "", {"name": "search", "args": {"q": "test"}}),
                ("tool_result", "", {"name": "search", "content": "results"}),
                ("text", "Here are the results", None),
            ])
            async for _ in tracker.track(stream, user_prompt="search for test"):
                pass
            return tracker

        t = asyncio.run(_run())
        # Get the final chain
        chain = t.path()

        # The chain should follow: user_input → llm_response → tool_call → tool_result → llm_response → state
        types = [n.node_type for n in chain]
        assert "user_input" in types
        assert "tool_call" in types
        assert "tool_result" in types
        assert "llm_response" in types
        assert "state_transition" in types

        # Check causal links
        for i in range(1, len(chain)):
            prev = chain[i - 1]
            curr = chain[i]
            assert curr.caused_by == prev.id, (
                f"{curr.node_type}({curr.id}) should be caused by "
                f"{prev.node_type}({prev.id})"
            )
