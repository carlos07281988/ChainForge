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
"""A2A integration layer — bootstrap A2A support into any ChainForge server.

Provides mount_a2a() to add A2A endpoints into an existing FastAPI app.

Usage:
    from chainforge.a2a.integration import mount_a2a

    app, router = mount_a2a(server_app, agents=my_agents, base_url="http://localhost:8000")
"""

from __future__ import annotations

from typing import Any

from chainforge.a2a.card import build_agent_card, AgentCard
from chainforge.a2a.server import A2ARouter
from chainforge.logging import get_logger

logger = get_logger("a2a.integration")


def mount_a2a(
    app: Any,
    *,
    agents: dict[str, Any] | None = None,
    base_url: str = "http://localhost:8000",
    card: AgentCard | None = None,
    prefix: str = "/a2a",
    version: str = "1.0",
) -> tuple[Any, A2ARouter | None]:
    """Mount A2A protocol endpoints into an existing FastAPI app.

    This is the main entry point for adding A2A support to a ChainForge
    HTTP server. Call it after you've created your agents.

    Args:
        app: A FastAPI application instance.
        agents: Dict of {agent_id: agent_instance} to expose via A2A.
        base_url: The public base URL of the server.
        card: Pre-built AgentCard. Auto-generated from agents if None.
        prefix: URL prefix for A2A endpoints (default: /a2a).
        version: A2A spec version.

    Returns:
        (app, A2ARouter | None) tuple.
    """
    if agents and card is None:
        first_id = next(iter(agents.keys()))
        first_agent = agents[first_id]
        card = build_agent_card(
            first_agent,
            name=_agent_name(first_id),
            description=str(type(first_agent).__name__),
            url=f"{base_url}{prefix}",
            version=version,
            streaming=True,
        )

    if card is None:
        card = AgentCard(
            name="ChainForgeA2A",
            description="A2A Agent",
            url=f"{base_url}{prefix}",
            version=version,
        )

    router = A2ARouter(agent_card=card)
    if agents:
        router.register_agents(**agents)

    fastapi_router = router.get_fastapi_router(prefix=prefix)
    app.include_router(fastapi_router)
    logger.info(f"A2A endpoints mounted at {base_url}{prefix}")

    return app, router


def _agent_name(agent_id: str) -> str:
    """Convert an agent ID to a human-readable name."""
    return agent_id.replace("_", " ").replace("-", " ").title()
