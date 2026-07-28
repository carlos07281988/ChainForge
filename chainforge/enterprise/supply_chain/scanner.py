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
"""SupplyChainScanner — scan agent tools, skills, and MCP servers."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from chainforge.enterprise.supply_chain.dependency import DependencyAnalyzer
from chainforge.enterprise.supply_chain.policy import PermissionPolicy
from chainforge.logging import get_logger

logger = get_logger("enterprise.supply_chain")


class SupplyChainReport(BaseModel):
    """Results of a supply chain security scan."""
    tools: list[dict[str, Any]] = Field(default_factory=list)
    skills: list[dict[str, Any]] = Field(default_factory=list)
    mcp_servers: list[dict[str, Any]] = Field(default_factory=list)
    total_risk_score: float = Field(default=0.0, ge=0.0, le=10.0)

    def to_json(self) -> dict[str, Any]:
        return self.model_dump()


class SupplyChainScanner:
    """Scan an agent's complete supply chain.

    Analyzes tools for import dependencies, inspects MCP server endpoints,
    and generates a risk score.

    Usage:
        scanner = SupplyChainScanner()
        report = scanner.scan(agent)
        print(f"Risk score: {report.total_risk_score}/10")
    """

    def __init__(self) -> None:
        self._dep_analyzer = DependencyAnalyzer()

    def scan(self, agent: Any) -> SupplyChainReport:
        """Scan an agent and return a SupplyChainReport.

        Args:
            agent: A ChainForge Agent instance.

        Returns:
            SupplyChainReport with tool/skill/MCP analysis.
        """
        tools: list[dict[str, Any]] = []
        skills: list[dict[str, Any]] = []
        mcp_servers: list[dict[str, Any]] = []
        risk_total: float = 0.0

        # Scan tools
        for tool in getattr(agent, "tools", []):
            try:
                callable_fn = getattr(tool, "_fn", tool)
                dep_info = self._dep_analyzer.analyze(callable_fn)

                # Risk scoring: dangerous imports
                dangerous = {"os", "subprocess", "shutil", "socket", "ctypes", "pickle"}
                tool_risk: float = sum(1 for imp in dep_info.imports if imp in dangerous) * 0.5
                risk_total += tool_risk

                tools.append({
                    "name": dep_info.name,
                    "imports": dep_info.imports,
                    "source_file": dep_info.source_file,
                    "risk_contributions": round(tool_risk, 1),
                })
            except Exception as e:
                logger.warning(f"Failed to scan tool: {e}")

        # Scan skills
        for skill in getattr(agent, "skills", []):
            try:
                dep_info = self._dep_analyzer.analyze(skill)
                skills.append({
                    "name": dep_info.name,
                    "imports": dep_info.imports,
                    "source_file": dep_info.source_file,
                })
            except Exception as e:
                logger.warning(f"Failed to scan skill: {e}")

        # MCP inventory
        mcp_config = getattr(agent, "_mcp_config", None)
        if mcp_config is not None and isinstance(mcp_config, dict):
            for server_name, server_cfg in mcp_config.items():
                url: str = server_cfg if isinstance(server_cfg, str) else server_cfg.get("url", str(server_cfg))
                mcp_risk: float = 0.0
                reason: str = ""
                if isinstance(url, str):
                    if any(domain in url for domain in ["api.", ".com", ".io", ".net"]):
                        mcp_risk = 1.0
                        reason = "External domain detected"
                    else:
                        reason = "Internal/local MCP server"
                mcp_servers.append({
                    "name": server_name,
                    "url": url,
                    "risk": "medium" if mcp_risk > 0 else "low",
                    "reason": reason,
                })
                risk_total += mcp_risk

        return SupplyChainReport(
            tools=tools,
            skills=skills,
            mcp_servers=mcp_servers,
            total_risk_score=round(min(risk_total, 10.0), 1),
        )

    def recommend_policy(self, agent: Any) -> PermissionPolicy:
        """Generate a minimal-permission policy for this agent.

        Analyzes which tools the agent actually calls and recommends
        allowing only those, blocking dangerous operations.

        Args:
            agent: A ChainForge Agent instance.

        Returns:
            PermissionPolicy with allowed and blocked tools.
        """
        allowed: list[str] = []
        blocked: list[str] = []

        dangerous_patterns = ["delete", "exec", "shell", "eval", "rm ", "kill"]

        for tool in getattr(agent, "tools", []):
            name: str = getattr(tool, "name", str(tool))
            if any(p in name.lower() for p in dangerous_patterns):
                blocked.append(name)
            else:
                allowed.append(name)

        return PermissionPolicy(
            allowed_tools=allowed,
            blocked_tools=blocked,
            mcp_constraints={},
        )
