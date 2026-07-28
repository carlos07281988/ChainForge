"""ChainForge Enterprise: Agent Personalization Engine example.

Usage:
    python examples/enterprise/personalize_example.py
"""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from chainforge.enterprise.personalize import (
    PersonalizationEngine, UserProfile, ResponseAdapter,
)

async def main():
    print("=== Agent Personalization Engine ===\n")

    engine = PersonalizationEngine()
    engine.create_tenant("acme-corp")
    engine.create_tenant("globex-inc")

    # 1. Learn preferences from interactions
    print("1. Learning User Preferences:")

    # Carlos (CEO, expert user)
    for q in ["Q3 revenue breakdown by region", "Cost optimization strategy", "Risk analysis summary"]:
        engine.record_interaction(user_id="carlos", query=q, feedback="positive", tenant_id="acme-corp")

    profile = engine.get_profile("carlos", "acme-corp")
    profile.preferences.preferred_style = "concise"
    profile.preferences.expertise_level = "expert"
    profile.preferences.tone_preference = "direct"
    profile.preferences.preferred_language = "zh"
    engine.update_profile(profile)

    print(f"   Carlos (CEO):")
    print(f"     Interactions: {profile.total_interactions}")
    print(f"     Style: {profile.preferences.preferred_style}")
    print(f"     Expertise: {profile.preferences.expertise_level}")
    print(f"     Tone: {profile.preferences.tone_preference}")
    print(f"     Satisfaction: {profile.satisfaction_rate:.0%}")

    # Alice (intern, novice user)
    for q in ["How do I get started?", "What is an API?", "Can you explain that more simply?"]:
        engine.record_interaction(user_id="alice", query=q, feedback="positive", tenant_id="acme-corp")

    alice = engine.get_profile("alice", "acme-corp")
    alice.preferences.preferred_style = "detailed"
    alice.preferences.expertise_level = "novice"
    alice.preferences.tone_preference = "friendly"
    engine.update_profile(alice)

    print(f"\n   Alice (Intern):")
    print(f"     Interactions: {alice.total_interactions}")
    print(f"     Style: {alice.preferences.preferred_style}")
    print(f"     Expertise: {alice.preferences.expertise_level}")

    # 2. Response Adapter -- personalized system hints
    adapter = ResponseAdapter(engine)

    hint_carlos = adapter.build_system_hint("carlos", "acme-corp")
    hint_alice = adapter.build_system_hint("alice", "acme-corp")
    print(f"\n2. Personalized System Hints:")
    print(f"   Carlos: \"{hint_carlos}\"")
    print(f"   Alice:  \"{hint_alice}\"")

    # Context-aware hint for short expert query
    expert_hint = adapter.get_hint_for_query("carlos", "Q3 numbers", "acme-corp")
    print(f"   Carlos (short Q): \"{expert_hint}\"")

    # 3. Multi-tenant isolation
    # Same user ID, different tenant -- completely separate profiles
    carlos_globex = engine.get_profile("carlos", "globex-inc")
    print(f"\n3. Multi-Tenant Isolation:")
    print(f"   Carlos @ acme-corp: {profile.total_interactions} interactions")
    print(f"   Carlos @ globex-inc: {carlos_globex.total_interactions} interactions")
    print(f"   (Same user ID, completely isolated profiles)")

    # 4. Export profiles
    data = engine.export_all()
    print(f"\n4. Export: {len(data)} user profiles ready for analytics")

if __name__ == "__main__":
    asyncio.run(main())
