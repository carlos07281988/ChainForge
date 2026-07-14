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
"""Tests for DAG graph module."""

import pytest

from chainforge.core.graph import DAG, Node, Edge, GraphContext


class TestDAG:
    def test_add_node(self):
        dag = DAG(name="test")
        dag.add_node("step1", fn=lambda x: x + 1)
        assert "step1" in dag.nodes
        assert dag.nodes["step1"].fn is not None

    def test_add_edge(self):
        dag = DAG(name="test")
        dag.add_node("a").add_node("b").add_edge("a", "b")
        assert len(dag.edges) == 1
        assert dag.edges[0].source == "a"
        assert dag.edges[0].target == "b"

    def test_add_edge_missing_node(self):
        dag = DAG(name="test")
        dag.add_node("a")
        with pytest.raises(ValueError, match="not found"):
            dag.add_edge("a", "missing")

    def test_topological_sort_linear(self):
        dag = DAG(name="test")
        dag.add_node("a").add_node("b").add_node("c")
        dag.add_edge("a", "b").add_edge("b", "c")
        order = dag._topological_sort()
        assert order == ["a", "b", "c"]

    def test_topological_sort_diamond(self):
        dag = DAG(name="test")
        dag.add_node("a").add_node("b").add_node("c").add_node("d")
        dag.add_edge("a", "b").add_edge("a", "c")
        dag.add_edge("b", "d").add_edge("c", "d")
        order = dag._topological_sort()
        assert order[0] == "a"
        assert order[-1] == "d"
        assert set(order[1:3]) == {"b", "c"}

    def test_cycle_detection(self):
        dag = DAG(name="test")
        dag.add_node("a").add_node("b")
        dag.add_edge("a", "b").add_edge("b", "a")
        with pytest.raises(ValueError, match="cycle"):
            dag._topological_sort()

    def test_entry_exit_nodes(self):
        dag = DAG(name="test")
        dag.add_node("a").add_node("b").add_node("c")
        dag.add_edge("a", "b").add_edge("b", "c")
        assert dag._get_entry_nodes() == ["a"]
        assert dag._get_exit_nodes() == ["c"]

    @pytest.mark.asyncio
    async def test_run_simple(self):
        dag = DAG(name="test")
        dag.add_node("double", fn=lambda x: x * 2)
        dag.add_node("add_one", fn=lambda x: x + 1)
        dag.add_edge("double", "add_one")

        stream = dag.run(5)
        events = await stream.collect()
        assert any(e.type.value == "done" for e in events)
        text_events = [e for e in events if e.type.value == "text"]
        assert len(text_events) > 0

    def test_plot(self):
        dag = DAG(name="test")
        dag.add_node("a").add_node("b").add_edge("a", "b")
        plot = dag.plot()
        assert "DAG: test" in plot
        assert "a" in plot
        assert "b" in plot

    def test_composition(self):
        dag1 = DAG(name="step1")
        dag1.add_node("double", fn=lambda x: x * 2)

        dag2 = DAG(name="step2")
        dag2.add_node("add_one", fn=lambda x: x + 1)

        combined = dag1 >> dag2
        assert "step1 >> step2" in combined.name


class TestGraphContext:
    def test_context_defaults(self):
        ctx = GraphContext()
        assert ctx.data == {}
        assert ctx.results == {}
        assert ctx.errors == []

    def test_context_with_data(self):
        ctx = GraphContext(data={"input": 42})
        assert ctx.data["input"] == 42
