"""ChainForge Enterprise: Agent Data Lineage & GDPR example.

Usage:
    python examples/enterprise/lineage_example.py
"""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from chainforge.enterprise.lineage import (
    DataLineageTracker, DataSubject, DataLocation,
    ErasureRequest, DeletionProof,
)

async def main():
    print("=== Agent Data Lineage & GDPR Right-to-Forget ===\n")

    tracker = DataLineageTracker(backend="memory")

    # 1. Simulate agent recording data locations
    subject = DataSubject(email="carlos@example.com", user_id="user-12345")
    tracker.record_location(subject, DataLocation(
        type="llm_response", provider="openai", identifier="call-abc-001",
        content_type="pii", deletable=True, deletion_method="api_delete"))
    tracker.record_location(subject, DataLocation(
        type="tool_result", provider="postgres", identifier="orders:row:42",
        content_type="pii", deletable=True, deletion_method="db_delete"))
    tracker.record_location(subject, DataLocation(
        type="s3_object", provider="aws", identifier="s3://logs/refund-carlos.json",
        content_type="partial_pii", deletable=True, deletion_method="api_delete"))
    tracker.record_location(subject, DataLocation(
        type="vector_memory", provider="qdrant", identifier="emb:collection:cust",
        content_type="derived", deletable=False, deletion_method="rebuild_collection"))
    tracker.record_location(subject, DataLocation(
        type="cache_entry", provider="redis", identifier="cache:refund:carlos",
        content_type="metadata", deletable=True, deletion_method="ttl_wait"))

    print("1. Data Footprint for carlos@example.com:")
    footprint = tracker.query(subject)
    print(f"   Total locations: {footprint.total_locations}")
    print(f"   Risk assessment: {footprint.risk_assessment}")
    for loc in footprint.locations:
        icon = "[DEL]" if loc.deletable else "[WT ]"
        print(f"   {icon} {loc.type} @ {loc.provider} -- {loc.deletion_method}")

    # 2. Execute GDPR erasure
    print("\n2. GDPR Erasure Request:")
    request = ErasureRequest(
        data_subjects=[{"email": "carlos@example.com", "user_id": "user-12345"}],
        reason="GDPR Article 17 -- Right to Erasure",
        requested_by="dpo@acme-corp.com",
        deadline_hours=72,
    )
    report = await tracker.erase(request)
    print(report.summary())

    # 3. Deletion Proof
    print("\n3. Deletion Proof:")
    proof = DeletionProof(report)
    print(f"   Proof hash: {proof.proof_hash[:16]}...")
    print(f"   Verified: {proof.verify()}")
    proof.export("/tmp/deletion-proof-example.json")
    print("   Exported to: /tmp/deletion-proof-example.json")
    os.unlink("/tmp/deletion-proof-example.json")

    # 4. Tracker stats
    print(f"\n4. Stats: {tracker.stats()}")

if __name__ == "__main__":
    asyncio.run(main())
