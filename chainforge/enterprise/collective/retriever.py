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
"""ExperienceRetriever — search and retrieve relevant past experiences."""
from __future__ import annotations
from chainforge.enterprise.collective.experience import Experience
from chainforge.enterprise.collective.memory import CollectiveMemory

class ExperienceRetriever:
    """Search shared memory for relevant past experiences.

    Usage:
        cm = CollectiveMemory()
        retriever = ExperienceRetriever(cm)
        similar = retriever.search("refund a customer order", limit=5)
    """

    def __init__(self, memory: CollectiveMemory):
        self._memory = memory

    def search(self, task: str, limit: int = 5,
               min_success_rate: float = 0.0) -> list[Experience]:
        """Find similar past experiences.

        Args:
            task: Current task description.
            limit: Max results.
            min_success_rate: Minimum success rate (0.0-1.0).

        Returns:
            Relevant past experiences, freshest first.
        """
        return self._memory.search(task, limit=limit, min_success_rate=min_success_rate)
