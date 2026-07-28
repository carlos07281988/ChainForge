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
"""Lineage query models — DataSubject, DataLocation, DataFootprint, LineageQuery."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field


class DataSubject(BaseModel):
    """A GDPR data subject identified by one or more identifiers."""

    user_id: str | None = None
    email: str | None = None
    phone: str | None = None
    ip_address: str | None = None


class DataLocation(BaseModel):
    """Where a data subject's information is stored."""

    type: str = ""          # llm_response|tool_result|vector_memory|cache|s3_object|email_log
    provider: str = ""      # openai|qdrant|postgres|s3|smtp
    identifier: str = ""    # Unique ID within that system
    content_type: str = ""  # pii|partial_pii|derived|metadata
    deletable: bool = True
    deletion_method: str = "api_delete"  # api_delete|db_delete|anonymize|ttl_wait
    extra: dict[str, Any] = Field(default_factory=dict)


class DataFootprint(BaseModel):
    """Complete footprint of a data subject across all systems."""

    subject: DataSubject
    locations: list[DataLocation] = Field(default_factory=list)
    total_locations: int = 0
    risk_assessment: str = "low"
    query_timestamp: float = Field(default_factory=lambda: time.time())

    def to_json(self) -> dict:
        return self.model_dump()


class LineageQuery(BaseModel):
    """Query parameters for finding a data subject's footprint."""

    data_subjects: list[DataSubject] = Field(default_factory=list)
    time_range: tuple[str, str] | None = None  # (start_iso, end_iso)
    location_types: list[str] | None = None     # filter by location type
    limit: int = 100
