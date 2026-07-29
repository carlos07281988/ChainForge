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
"""Collective Agent Memory — shared experiences, retrieval, and conflict resolution."""

from chainforge.enterprise.collective.experience import Experience
from chainforge.enterprise.collective.forgetting import ForgettingCurve
from chainforge.enterprise.collective.memory import CollectiveMemory
from chainforge.enterprise.collective.recorder import ExperienceRecorder
from chainforge.enterprise.collective.retriever import ExperienceRetriever
from chainforge.enterprise.collective.resolver import ConflictResolver, ConflictResolution

__all__ = [
    "Experience",
    "ForgettingCurve",
    "CollectiveMemory",
    "ExperienceRecorder",
    "ExperienceRetriever",
    "ConflictResolver",
    "ConflictResolution",
]
