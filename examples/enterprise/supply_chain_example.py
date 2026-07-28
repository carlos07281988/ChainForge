"""ChainForge Enterprise: Agent Supply Chain Security example.

Usage:
    python examples/enterprise/supply_chain_example.py
"""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from chainforge.enterprise.supply_chain import (
    SupplyChainScanner, PermissionPolicy, SBOMExporter, SupplyChainReport,
)

async def main():
    print("=== Agent Supply Chain Security ===\n")

    # 1. Build a SupplyChainReport directly (no live agent needed)
    report = SupplyChainReport(
        tools=[
            {"name": "query_db", "imports": ["psycopg2", "sqlalchemy"], "source_file": "tools/db.py", "risk_contributions": 0.0},
            {"name": "send_email", "imports": ["smtplib", "email"], "source_file": "tools/email.py", "risk_contributions": 0.0},
            {"name": "delete_file", "imports": ["os", "shutil"], "source_file": "tools/file_ops.py", "risk_contributions": 1.0},
        ],
        skills=[],
        mcp_servers=[
            {"name": "weather-api", "url": "http://mcp-weather:8080", "risk": "medium",
             "reason": "External domain api.weather.com detected"},
        ],
        total_risk_score=3.5,
    )
    print("1. Supply Chain Scan:")
    print(f"   Risk score: {report.total_risk_score}/10")
    for t in report.tools:
        risk_icon = "[!]" if t.get("risk_contributions", 0) > 0 else "[OK]"
        print(f"   {risk_icon} {t['name']}: risk={t['risk_contributions']}")
    for m in report.mcp_servers:
        print(f"   [!] MCP {m['name']}: {m['risk']} risk -- {m['reason']}")

    # 2. Permission Policy
    policy = PermissionPolicy(
        allowed_tools=["query_db", "send_email"],
        blocked_tools=["delete_file"],
        mcp_constraints={"weather-api": {"max_data_transfer_mb": 1, "allow_external": False}},
    )
    print("\n2. Permission Policy:")
    print(f"   Allowed: {policy.allowed_tools}")
    print(f"   Blocked: {policy.blocked_tools}")
    yaml_str = policy.to_yaml()
    print(f"   YAML export (first 100 chars): {yaml_str[:100]}...")

    # 3. SBOM Export
    import types

    class FakeAgent:
        def __init__(self):
            self.tools = [
                types.SimpleNamespace(name="query_db"),
                types.SimpleNamespace(name="send_email"),
                types.SimpleNamespace(name="delete_file"),
            ]
            self.skills = []

    agent = FakeAgent()
    sbom = SBOMExporter().export(agent, format="spdx")
    print("\n3. SBOM Export:")
    data = sbom.to_json()
    print(f"   Format: {sbom.format}")
    print(f"   Packages: {len(data.get('packages', []))}")
    print(f"   SPDX version: {data.get('spdxVersion', 'N/A')}")

    sbom2 = SBOMExporter().export(agent, format="cyclonedx")
    cd_data = sbom2.to_json()
    print(f"   CycloneDX: {len(cd_data.get('components', []))} components")
    print(f"   Spec version: {cd_data.get('specVersion', 'N/A')}")

if __name__ == "__main__":
    asyncio.run(main())
