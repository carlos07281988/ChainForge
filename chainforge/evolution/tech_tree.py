"""Technology Tree — unlock agent capabilities through usage.

Like a Civilization game tech tree: agents earn capabilities by using tools,
completing tasks, and accumulating experience. Each node in the tree represents
a capability that unlocks when conditions are met.

Usage:
    tree = TechTree()
    tree.add_node("basic_search", "Basic Search", "Use search tools", unlocks="search_basic")
    tree.add_node("advanced_search", "Advanced Search", "10 searches required",
                  requires=["basic_search"], unlocks="search_advanced")
    tree.record_usage("search")
    unlocked = tree.check_unlocks()
"""

from __future__ import annotations

import time
from typing import Any, Callable

from pydantic import BaseModel, Field


class TechNode(BaseModel):
    """A single node in the technology tree."""

    id: str = Field(description="Unique node identifier")
    name: str = Field(description="Display name")
    description: str = Field(default="")
    requires: list[str] = Field(default_factory=list, description="Required parent node IDs")
    unlocks: str | None = Field(default=None, description="Capability unlocked by this node")
    unlock_condition: str | None = Field(default=None, description="Human-readable condition")
    required_count: int = Field(default=0, description="Required tool uses to unlock")
    required_tool: str | None = Field(default=None, description="Specific tool to track")
    is_unlocked: bool = Field(default=False)
    unlocked_at: float | None = Field(default=None)
    icon: str = Field(default="🔒")


class TechTree(BaseModel):
    """A technology tree of agent capabilities."""

    nodes: dict[str, TechNode] = Field(default_factory=dict)
    usage_counts: dict[str, int] = Field(default_factory=dict, description="Tool usage counter")
    listeners: list[Callable] = Field(default_factory=list, exclude=True)

    def add_node(
        self,
        node_id: str,
        name: str,
        description: str = "",
        *,
        requires: list[str] | None = None,
        unlocks: str | None = None,
        required_count: int = 0,
        required_tool: str | None = None,
        icon: str = "🔒",
    ) -> "TechTree":
        self.nodes[node_id] = TechNode(
            id=node_id, name=name, description=description,
            requires=requires or [], unlocks=unlocks,
            required_count=required_count, required_tool=required_tool,
            icon=icon,
        )
        return self

    def record_usage(self, tool_name: str) -> list[TechNode]:
        """Record a tool usage and check for unlocks. Returns newly unlocked nodes."""
        self.usage_counts[tool_name] = self.usage_counts.get(tool_name, 0) + 1
        return self.check_unlocks()

    def record_success(self, task_type: str) -> list[TechNode]:
        """Record a successful task completion."""
        key = f"_success_{task_type}"
        self.usage_counts[key] = self.usage_counts.get(key, 0) + 1
        return self.check_unlocks()

    def check_unlocks(self) -> list[TechNode]:
        """Check all locked nodes and unlock any that meet conditions."""
        newly_unlocked = []
        for node in self.nodes.values():
            if node.is_unlocked:
                continue

            # Check requirements
            if node.requires:
                if not all(self.nodes.get(r) and self.nodes[r].is_unlocked for r in node.requires):
                    continue

            # Check usage condition
            if node.required_count > 0:
                tool = node.required_tool
                if tool:
                    count = self.usage_counts.get(tool, 0)
                else:
                    count = sum(self.usage_counts.values())
                if count < node.required_count:
                    continue

            # Unlock!
            node.is_unlocked = True
            node.unlocked_at = time.time()
            newly_unlocked.append(node)

            # Fire listeners
            for listener in self.listeners:
                try:
                    listener(node)
                except Exception:
                    pass

        return newly_unlocked

    def on_unlock(self, listener: Callable[[TechNode], None]) -> Callable:
        """Register a callback for when nodes are unlocked."""
        self.listeners.append(listener)
        return lambda: self.listeners.remove(listener)

    def get_unlocked_ids(self) -> list[str]:
        """Return IDs of all unlocked nodes."""
        return [nid for nid, n in self.nodes.items() if n.is_unlocked]

    def get_locked_ids(self) -> list[str]:
        """Return IDs of all locked nodes."""
        return [nid for nid, n in self.nodes.items() if not n.is_unlocked]

    def get_next_available(self) -> list[TechNode]:
        """Return locked nodes that could be unlocked next (all requirements met)."""
        available = []
        for node in self.nodes.values():
            if node.is_unlocked:
                continue
            # If no requirements or all requirements met
            if not node.requires or all(
                self.nodes.get(r) and self.nodes[r].is_unlocked for r in node.requires
            ):
                available.append(node)
        return available

    def progress(self) -> float:
        """Return completion percentage."""
        if not self.nodes:
            return 0.0
        return sum(1 for n in self.nodes.values() if n.is_unlocked) / len(self.nodes)

    def plot(self) -> str:
        """Return an ASCII visualization of the tech tree."""
        lines = ["Technology Tree:", "=" * 40]
        # Group by depth
        unlocked = self.get_unlocked_ids()
        for nid, node in self.nodes.items():
            status = "✅" if node.is_unlocked else "🔒"
            reqs = f" (needs: {', '.join(node.requires)})" if node.requires else ""
            count_info = ""
            if node.required_count > 0:
                current = self.usage_counts.get(node.required_tool or "_total", 0)
                count_info = f" [{current}/{node.required_count}]"
            lines.append(f"  {status} {node.icon} {node.name}{count_info}{reqs}")
        lines.append("=" * 40)
        lines.append(f"Progress: {self.progress() * 100:.0f}% ({len(unlocked)}/{len(self.nodes)})")
        return "\n".join(lines)


def default_tech_tree() -> TechTree:
    """Create a default technology tree for common agent capabilities."""
    tree = TechTree()

    # Tier 1: Basic tools
    tree.add_node("search", "Search", "Ability to search the web",
                  unlocks="search_tool", icon="🔍")
    tree.add_node("calculate", "Calculate", "Ability to perform calculations",
                  unlocks="calc_tool", icon="🔢")
    tree.add_node("memory", "Memory", "Conversation memory support",
                  unlocks="memory_tool", icon="🧠")

    # Tier 2: Advanced tools (requires Tier 1)
    tree.add_node("advanced_search", "Advanced Search", "Search with filters and ranking",
                  requires=["search"], required_count=10, required_tool="search",
                  icon="🔎")
    tree.add_node("data_analysis", "Data Analysis", "Analyze and visualize data",
                  requires=["calculate"], required_count=5, required_tool="calculate",
                  icon="📊")

    # Tier 3: Expert capabilities (requires Tier 2)
    tree.add_node("report_gen", "Report Generation", "Generate structured reports",
                  requires=["advanced_search", "data_analysis"],
                  icon="📄")
    tree.add_node("code_gen", "Code Generation", "Generate and execute code",
                  requires=["data_analysis"], required_count=10,
                  icon="💻")

    # Tier 4: Master capabilities
    tree.add_node("autonomous", "Autonomous Mode", "Self-directed task execution",
                  requires=["report_gen", "code_gen"],
                  icon="🤖")

    return tree


__all__ = ["TechTree", "TechNode", "default_tech_tree"]
