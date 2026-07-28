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
"""GraphExtractor — Middleware that auto-extracts entities and relations from agent conversations.

Stub implementation — production version uses LLM-based NER + relation extraction
to build knowledge graphs from natural language agent interactions.
"""

from __future__ import annotations

from chainforge.enterprise.graphrag.engine import GraphRAGEngine


class GraphExtractor:
    """Middleware that auto-extracts entities and relations from agent conversations.

    Stub implementation — production version uses LLM-based NER + relation extraction
    to build knowledge graphs from natural language agent interactions.
    """

    def __init__(self, engine: GraphRAGEngine):
        self._engine = engine

    def middleware(self):
        async def _mw(messages, ctx, next_handler):
            async for event in next_handler(messages, ctx):
                yield event

        return _mw
