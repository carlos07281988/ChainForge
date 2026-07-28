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
"""MCPVerifier — verify MCP server behavior and security posture."""
from __future__ import annotations

from urllib.parse import urlparse

from pydantic import BaseModel, Field


class MCPVerification(BaseModel):
    """Result of an MCP server security verification."""
    url: str = ""
    reachable: bool = False
    risk: str = "unknown"  # low | medium | high
    data_exfiltration_risk: bool = False
    domains_contacted: list[str] = Field(default_factory=list)
    notes: str = ""


class MCPVerifier:
    """Verify MCP server security posture.

    Performs lightweight checks on MCP server endpoints:
    - Is it reachable?
    - Does it resolve to an external domain?
    - Data exfiltration risk assessment

    Usage:
        verifier = MCPVerifier()
        result = await verifier.verify("http://mcp-server:8080")
        print(f"Risk: {result.risk}")
    """

    def __init__(self) -> None:
        self._results: list[MCPVerification] = []

    async def verify(self, url: str, timeout: float = 5.0) -> MCPVerification:
        """Verify a single MCP server endpoint.

        Args:
            url: MCP server URL.
            timeout: Request timeout in seconds.

        Returns:
            MCPVerification with risk assessment.
        """
        reachable: bool = False
        risk: str = "low"
        notes: str = ""
        domains: list[str] = []

        try:
            import httpx
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(f"{url.rstrip('/')}/health")
                reachable = resp.status_code == 200
        except Exception:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.get(url)
                    reachable = resp.status_code < 500
            except Exception as e:
                notes = f"Not reachable: {e}"

        # Domain analysis
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        domains.append(hostname)

        # External domain detection
        external_indicators = [".com", ".io", ".net", ".org", "api.", "cloud"]
        is_external = any(ind in hostname for ind in external_indicators)
        data_exfil_risk: bool = is_external

        if is_external:
            risk = "medium"
            notes = f"External domain detected: {hostname}. Data may leave your network."

        result = MCPVerification(
            url=url,
            reachable=reachable,
            risk=risk,
            data_exfiltration_risk=data_exfil_risk,
            domains_contacted=domains,
            notes=notes,
        )
        self._results.append(result)
        return result

    @property
    def results(self) -> list[MCPVerification]:
        return list(self._results)
