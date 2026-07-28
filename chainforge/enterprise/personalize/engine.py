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
"""Personalization engine — learns and applies user-level preferences for multi-tenant agents."""

from __future__ import annotations

from chainforge.enterprise.personalize.profile import UserProfile
from chainforge.logging import get_logger

logger = get_logger("enterprise.personalize")


class PersonalizationEngine:
    """Learn and apply user-level preferences for multi-tenant agent personalization.

    Usage::

        engine = PersonalizationEngine()
        agent = Agent(llm=llm, middlewares=[engine.middleware()])

        profile = engine.get_profile(user_id="carlos")
        profile.preferences.preferred_style = "concise"
        engine.update_profile(profile)
    """

    def __init__(self, backend: str = "memory"):
        self._backend = backend
        self._profiles: dict[str, UserProfile] = {}
        self._tenants: set[str] = {"default"}

    def create_tenant(self, tenant_id: str) -> None:
        self._tenants.add(tenant_id)

    def get_profile(self, user_id: str, tenant_id: str = "default") -> UserProfile:
        key = f"{tenant_id}:{user_id}"
        if key not in self._profiles:
            self._profiles[key] = UserProfile(user_id=user_id, tenant_id=tenant_id)
        return self._profiles[key]

    def update_profile(self, profile: UserProfile) -> None:
        key = f"{profile.tenant_id}:{profile.user_id}"
        self._profiles[key] = profile

    def record_interaction(
        self,
        user_id: str,
        query: str,
        feedback: str | None = None,
        tenant_id: str = "default",
    ) -> UserProfile:
        profile = self.get_profile(user_id, tenant_id)
        profile.record_interaction(query=query, feedback=feedback)
        self.update_profile(profile)
        return profile

    def get_tenant_profiles(self, tenant_id: str) -> list[UserProfile]:
        return [p for k, p in self._profiles.items() if p.tenant_id == tenant_id]

    def middleware(self):
        """Middleware for auto-learning user preferences during agent runs."""
        engine = self

        async def _mw(messages, ctx, next_handler):
            user_id = ctx.get("user_id", "anonymous")
            tenant_id = ctx.get("tenant_id", "default")
            query = ""
            if messages:
                last = messages[-1]
                query = str(last.content) if hasattr(last, "content") else ""
            async for event in next_handler(messages, ctx):
                yield event
            try:
                engine.record_interaction(user_id=user_id, query=query, tenant_id=tenant_id)
            except Exception as e:
                logger.debug(f"Personalization record failed: {e}")

        return _mw

    @property
    def stats(self) -> dict:
        profiles = list(self._profiles.values())
        avg_sat = sum(p.satisfaction_rate for p in profiles) / max(len(profiles), 1)
        return {
            "total_users": len(profiles),
            "tenants": len(self._tenants),
            "avg_satisfaction": round(avg_sat, 2),
            "new_users": sum(1 for p in profiles if p.is_new_user),
        }

    def export_all(self) -> list[dict]:
        return [p.to_json() for p in self._profiles.values()]
