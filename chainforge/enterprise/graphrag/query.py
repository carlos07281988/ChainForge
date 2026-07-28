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
"""GraphRAG 3.0 query models — GraphQuery and GraphQLQuery."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class GraphQuery(BaseModel):
    """A structured query against the knowledge graph."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    node_type: str | None = None
    label_contains: str | None = None
    relation_type: str | None = None
    limit: int = 10


class GraphQLQuery(BaseModel):
    """A GraphQL query for the knowledge graph."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    query: str = ""
    node_type: str | None = None
    limit: int = 100
