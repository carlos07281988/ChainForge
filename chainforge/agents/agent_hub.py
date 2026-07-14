# Copyright 2024 ChainForge Contributors
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
"""AgentHub — 注册、发现、组合 Agent。

提供中心化的 Agent 注册表，支持按名称/描述/标签发现，
以及自动创建 RouterAgent 来路由请求。
"""

from __future__ import annotations

from logging import INFO
from typing import Any

from chainforge.logging import get_logger, log_data

logger = get_logger("agents.agent_hub")


class AgentEntry:
    """A registered agent with metadata."""

    def __init__(self, name: str, agent: Any, description: str = "", tags: list[str] | None = None):
        self.name = name
        self.agent = agent
        self.description = description
        self.tags = tags or []


class AgentHub:
    """Central registry for discovering and composing agents.

    Usage:
        hub = AgentHub()
        hub.register("search", search_agent, "Search the web", tags=["research"])
        hub.register("calc", calc_agent, "Do math", tags=["tools"])

        # Get an agent
        agent = hub.get("search")

        # Create a router from all registered agents
        router = hub.create_router(classifier_llm=llm)
        stream = await router.run("What is the weather?")
    """

    def __init__(self):
        self._agents: dict[str, AgentEntry] = {}

    # ── Registration ──────────────────────────────────────────────────────

    def register(self, name: str, agent: Any, description: str = "", tags: list[str] | None = None) -> "AgentHub":
        """Register an agent with metadata."""
        self._agents[name] = AgentEntry(name=name, agent=agent, description=description, tags=tags or [])
        log_data(logger, INFO, f"Agent registered: {name}", data={"name": name, "tags": tags})
        return self

    def unregister(self, name: str) -> None:
        """Remove an agent from the hub."""
        self._agents.pop(name, None)

    # ── Discovery ─────────────────────────────────────────────────────────

    def get(self, name: str) -> Any | None:
        """Get an agent by name."""
        entry = self._agents.get(name)
        return entry.agent if entry else None

    def list(self) -> list[dict[str, Any]]:
        """List all registered agents with metadata."""
        return [
            {"name": e.name, "description": e.description, "tags": e.tags}
            for e in self._agents.values()
        ]

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search agents by name or description."""
        q = query.lower()
        results = []
        for e in self._agents.values():
            if q in e.name.lower() or q in e.description.lower():
                results.append({"name": e.name, "description": e.description, "tags": e.tags})
            else:
                for tag in e.tags:
                    if q in tag.lower():
                        results.append({"name": e.name, "description": e.description, "tags": e.tags})
                        break
        return results

    def find_by_tag(self, tag: str) -> list[dict[str, Any]]:
        """Find agents by tag."""
        return [
            {"name": e.name, "description": e.description, "tags": e.tags}
            for e in self._agents.values()
            if tag in e.tags
        ]

    # ── Composition ───────────────────────────────────────────────────────

    def create_router(self, classifier_llm: Any, default_route: str | None = None) -> Any:
        """Create a RouterAgent from all registered agents.

        Each agent becomes a route. Uses the agent's description for intent matching.
        """
        from chainforge.agents.router import RouterAgent

        routes = {}
        for name, entry in self._agents.items():
            routes[name] = entry.agent

        return RouterAgent(
            classifier_llm=classifier_llm,
            routes=routes,
            default_route=default_route or (list(routes.keys())[0] if routes else ""),
        )

    def create_chain(self, step_names: list[str], name: str = "hub_chain") -> Any:
        """Create an AgentChain from registered agents by name.

        Args:
            step_names: Ordered list of agent names to chain.
            name: Name for the chain.
        """
        from chainforge.agents.agent_chain import AgentChain

        chain = AgentChain(name=name)
        for sname in step_names:
            agent = self.get(sname)
            if agent:
                entry = self._agents[sname]
                chain.add_step(sname, agent, entry.description)
        return chain

    def summary(self) -> str:
        """Return a human-readable summary of all agents."""
        lines = [f"AgentHub: {len(self._agents)} agents registered", "=" * 40]
        for e in self._agents.values():
            tags = f" [{', '.join(e.tags)}]" if e.tags else ""
            lines.append(f"  {e.name}: {e.description}{tags}")
        return "\n".join(lines)

    @property
    def count(self) -> int:
        return len(self._agents)

    def clear(self) -> None:
        self._agents.clear()
