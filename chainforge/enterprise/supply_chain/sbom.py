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
"""SBOMExporter — generate Software Bill of Materials for agents."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class SBOMExporter:
    """Export a Software Bill of Materials (SBOM) for an agent.

    Generates SPDX 2.3 or CycloneDX 1.5 format SBOM documents.

    Usage:
        sbom = SBOMExporter().export(agent, format="spdx")
        sbom.save("sbom.my_agent.spdx.json")
    """

    def export(self, agent: Any, format: str = "spdx") -> "SBOMDocument":
        """Generate an SBOM for the given agent.

        Args:
            agent: A ChainForge Agent instance.
            format: "spdx" or "cyclonedx".

        Returns:
            SBOMDocument ready for serialization.
        """
        packages: list[dict[str, Any]] = []
        tool_names: list[str] = [getattr(t, "name", str(t)) for t in getattr(agent, "tools", [])]

        for tool in getattr(agent, "tools", []):
            name: str = getattr(tool, "name", str(tool))
            packages.append({
                "name": name,
                "versionInfo": "1.0.0",
                "supplier": "ChainForge Agent",
                "type": "tool",
            })

        for skill in getattr(agent, "skills", []):
            name = getattr(skill, "name", str(skill))
            packages.append({
                "name": name,
                "versionInfo": "1.0.0",
                "supplier": "ChainForge Skill",
                "type": "skill",
            })

        if format == "spdx":
            doc = self._build_spdx(packages, tool_names)
        else:
            doc = self._build_cyclonedx(packages, tool_names)

        return SBOMDocument(content=doc, format=format)

    def _build_spdx(self, packages: list[dict[str, Any]], tool_names: list[str]) -> dict[str, Any]:
        return {
            "spdxVersion": "SPDX-2.3",
            "dataLicense": "CC0-1.0",
            "SPDXID": "SPDXRef-DOCUMENT",
            "documentNamespace": f"https://chainforge.dev/sbom/{int(time.time())}",
            "name": "ChainForge Agent SBOM",
            "creationInfo": {
                "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "creators": ["Tool: ChainForge SBOMExporter"],
            },
            "packages": [
                {
                    "name": p["name"],
                    "SPDXID": f"SPDXRef-{p['name']}",
                    "versionInfo": p["versionInfo"],
                    "supplier": p["supplier"],
                }
                for p in packages
            ],
            "relationships": [
                {
                    "spdxElementId": "SPDXRef-DOCUMENT",
                    "relatedSpdxElement": f"SPDXRef-{name}",
                    "relationshipType": "CONTAINS",
                }
                for name in tool_names
            ],
        }

    def _build_cyclonedx(self, packages: list[dict[str, Any]], tool_names: list[str]) -> dict[str, Any]:
        return {
            "bomFormat": "CycloneDX",
            "specVersion": "1.5",
            "version": 1,
            "metadata": {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "tools": [{"vendor": "ChainForge", "name": "SBOMExporter"}],
            },
            "components": [
                {"type": "application", "name": p["name"], "version": p["versionInfo"]}
                for p in packages
            ],
        }


class SBOMDocument:
    """A generated SBOM document."""

    def __init__(self, content: dict[str, Any], format: str) -> None:
        self._content = content
        self._format = format

    @property
    def format(self) -> str:
        return self._format

    def to_json(self) -> dict[str, Any]:
        return dict(self._content)

    def save(self, path: str) -> None:
        """Write the SBOM to a JSON file."""
        Path(path).write_text(json.dumps(self._content, indent=2), encoding="utf-8")
