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
"""User behavior profile and learned preference vector for a single user."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PreferenceVector(BaseModel):
    """Learned preferences for a single user."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    preferred_style: str = "balanced"      # concise|balanced|detailed|verbose
    preferred_language: str = "auto"       # en|zh|auto
    expertise_level: str = "intermediate"  # novice|intermediate|expert
    tone_preference: str = "neutral"       # formal|neutral|casual|friendly
    max_response_length: int = 0           # 0=no preference
    common_topics: list[str] = Field(default_factory=list)
    avg_query_length: float = 0.0


class UserProfile(BaseModel):
    """Complete behavioral profile for a single user."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    user_id: str = ""
    tenant_id: str = Field(default="default")
    preferences: PreferenceVector = Field(default_factory=PreferenceVector)
    total_interactions: int = 0
    total_feedback_positive: int = 0
    total_feedback_negative: int = 0
    last_seen_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def satisfaction_rate(self) -> float:
        if self.total_interactions == 0:
            return 0.5
        return self.total_feedback_positive / max(self.total_interactions, 1)

    @property
    def is_new_user(self) -> bool:
        return self.total_interactions == 0 and (time.time() - self.created_at) < 86400

    def record_interaction(self, query: str | None = None, feedback: str | None = None) -> None:
        """Update profile counters based on user interaction."""
        self.total_interactions += 1
        self.last_seen_at = time.time()
        if feedback == "positive":
            self.total_feedback_positive += 1
        elif feedback == "negative":
            self.total_feedback_negative += 1
        if query:
            self.preferences.avg_query_length = (
                self.preferences.avg_query_length * (self.total_interactions - 1)
                + len(query.split())
            ) / self.total_interactions

    def to_json(self) -> dict:
        return self.model_dump()

    @classmethod
    def load(cls, path: str) -> "UserProfile":
        data = json.loads(Path(path).read_text())
        pv = PreferenceVector(**data.pop("preferences", {}))
        return cls(**data, preferences=pv)

    def save(self, path: str) -> None:
        Path(path).write_text(json.dumps(self.model_dump(), indent=2, default=str), encoding="utf-8")
