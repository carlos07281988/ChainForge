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
"""ForgettingCurve — time-based experience decay algorithms."""
from __future__ import annotations
import math

class ForgettingCurve:
    """Time-decay functions for aging experiences.

    Usage:
        factor = ForgettingCurve.ebbinghaus(days_since=7.0)
        # → ~0.59 (experience is ~59% relevant after 7 days)
    """
    @staticmethod
    def ebbinghaus(days_since: float, half_life: float = 7.0) -> float:
        """Ebbinghaus-inspired decay: relevance halves every `half_life` days."""
        if days_since <= 0: return 1.0
        return max(0.05, math.exp(-0.693 * days_since / half_life))

    @staticmethod
    def linear(days_since: float, max_days: float = 30.0) -> float:
        """Linear decay from 1.0 at day 0 to 0.0 at max_days."""
        if days_since <= 0: return 1.0
        if days_since >= max_days: return 0.0
        return 1.0 - (days_since / max_days)

    @staticmethod
    def none(days_since: float) -> float:
        """No decay — experience never expires."""
        return 1.0
