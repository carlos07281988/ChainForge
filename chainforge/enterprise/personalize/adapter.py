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
"""Response adapter — adapts agent responses based on learned user preferences."""

from __future__ import annotations

from chainforge.enterprise.personalize.engine import PersonalizationEngine
from chainforge.enterprise.personalize.profile import UserProfile
from chainforge.logging import get_logger

logger = get_logger("enterprise.personalize.adapter")


class ResponseAdapter:
    """Adapt agent responses based on user preferences.

    Usage::

        adapter = ResponseAdapter(engine)
        adapted_prompt = adapter.build_system_hint(user_id="carlos")
        # -> "User preferences: concise style, expert level, direct tone."
        # Inject this into the agent's system prompt for personalized responses.
    """

    def __init__(self, engine: PersonalizationEngine):
        self._engine = engine

    def build_system_hint(self, user_id: str, tenant_id: str = "default") -> str:
        """Generate a system prompt hint based on learned user preferences.

        Returns a string suitable for appending to the agent's system prompt.
        """
        profile = self._engine.get_profile(user_id, tenant_id)
        if profile.is_new_user:
            return ""
        p = profile.preferences
        hints: list[str] = []
        if p.preferred_style != "balanced":
            hints.append(f"Use a {p.preferred_style} writing style")
        if p.preferred_language != "auto":
            hints.append(f"Respond in {p.preferred_language}")
        if p.expertise_level == "novice":
            hints.append("Use simple language, avoid jargon")
        elif p.expertise_level == "expert":
            hints.append("Use technical language, go deep")
        if p.tone_preference != "neutral":
            hints.append(f"Use a {p.tone_preference} tone")
        if p.max_response_length > 0:
            hints.append(f"Keep responses under ~{p.max_response_length} words")
        if hints:
            return "User preferences: " + "; ".join(hints) + "."
        return ""

    def get_user_profile(self, user_id: str, tenant_id: str = "default") -> UserProfile:
        return self._engine.get_profile(user_id, tenant_id)

    def get_hint_for_query(self, user_id: str, query: str, tenant_id: str = "default") -> str:
        """Generate a hint that is context-aware based on the query content.

        Short queries from expert users -> even more concise response hint.
        """
        hint = self.build_system_hint(user_id, tenant_id)
        profile = self._engine.get_profile(user_id, tenant_id)
        words = len(query.split())
        if profile.preferences.expertise_level == "expert" and words < 10:
            hint += " (User is asking a short question — be direct and skip explanations.)"
        return hint
