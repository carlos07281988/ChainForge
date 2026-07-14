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
"""Agent Card generation — build A2A AgentCards from ChainForge Agents."""

from __future__ import annotations

from typing import Any

from chainforge.a2a.types import (
    AgentAuthentication,
    AgentCapabilities,
    AgentCard,
    AgentProvider,
    Skill,
)


def build_agent_card(
    agent: Any,
    *,
    name: str | None = None,
    description: str | None = None,
    url: str = "",
    version: str = "1.0",
    provider: str | None = None,
    provider_url: str | None = None,
    streaming: bool = True,
    auth: str | None = None,
) -> AgentCard:
    """Build an A2A AgentCard from a ChainForge Agent (or any compatible agent).

    Args:
        agent: A ChainForge Agent (or any object with tools, skills, system_prompt attrs).
        name: Agent name. Defaults to type name or "agent".
        description: Agent description. Defaults to system prompt or "".
        url: Base URL where this agent is reachable.
        version: A2A spec version.
        provider: Provider name.
        provider_url: Provider URL.
        streaming: Whether the agent supports SSE streaming.
        auth: Authentication scheme name (e.g. "bearer"). None = no auth.

    Returns:
        An AgentCard ready to be served via the A2A endpoint.
    """
    agent_name = name or type(agent).__name__
    agent_desc = description or getattr(agent, "system_prompt", None) or ""

    # ── Build skills from tools ───────────────────────────────────────────
    skills: list[Skill] = []
    tools = _get_tools(agent)
    for t in tools:
        spec = t.spec if hasattr(t, "spec") else None
        if spec:
            skills.append(Skill(
                id=spec.name,
                name=spec.name,
                description=spec.description or "",
                tags=["tool"],
                examples=[],
            ))

    # ── Build skills from ChainForge skills ───────────────────────────────
    agent_skills = getattr(agent, "skills", []) or []
    for s in agent_skills:
        sk_name = getattr(s, "name", type(s).__name__)
        sk_desc = getattr(s, "description", "") or str(s)[:100]
        skills.append(Skill(
            id=f"skill:{sk_name}",
            name=sk_name,
            description=sk_desc,
            tags=["skill"],
        ))

    # ── Agent-level skill from system prompt ──────────────────────────────
    if agent_desc:
        skills.insert(0, Skill(
            id="agent:main",
            name=agent_name,
            description=agent_desc[:200],
            tags=["agent", "general"],
        ))

    # ── Capabilities ──────────────────────────────────────────────────────
    capabilities = AgentCapabilities(
        streaming=streaming,
        push_notifications=False,
    )

    authentication = None
    if auth:
        authentication = AgentAuthentication(schemes=[auth])

    provider_info = None
    if provider:
        provider_info = AgentProvider(name=provider, url=provider_url)

    return AgentCard(
        name=agent_name,
        description=agent_desc[:500] if agent_desc else None,
        url=url,
        provider=provider_info,
        version=version,
        capabilities=capabilities,
        skills=skills,
        authentication=authentication,
    )


def _get_tools(agent: Any) -> list:
    """Extract tool list from an agent-like object."""
    if hasattr(agent, "_all_tools"):
        return agent._all_tools()
    if hasattr(agent, "tools"):
        return list(agent.tools) if isinstance(agent.tools, (list, tuple)) else []
    return []
