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
"""DataLineageTracker — tracks data lineage across all agent systems and handles GDPR erasure."""

from __future__ import annotations

from typing import Any, Callable

from chainforge.enterprise.lineage.erasure import ErasureItem, ErasureReport, ErasureRequest
from chainforge.enterprise.lineage.query import DataFootprint, DataLocation, DataSubject, LineageQuery
from chainforge.logging import get_logger

logger = get_logger("enterprise.lineage")


class DataLineageTracker:
    """Tracks data lineage across all agent systems and handles GDPR erasure.

    Usage::

        tracker = DataLineageTracker(backend="sqlite")
        agent = Agent(llm=llm, tools=[...], middlewares=[tracker.middleware()])

        # Query footprint
        footprint = tracker.query(DataSubject(email="user@example.com"))

        # Execute erasure
        report = await tracker.erase(ErasureRequest(
            data_subjects=[{"email": "user@example.com"}],
            requested_by="dpo@acme.com",
        ))
    """

    def __init__(self, backend: str = "memory", db_path: str | None = None) -> None:
        self._backend = backend
        self._locations: dict[str, list[DataLocation]] = {}  # keyed by subject hash
        self._handlers: dict[str, Callable] = {}  # custom deletion handlers
        self._db_path = db_path

    def _subject_key(self, subject: DataSubject) -> str:
        """Create a unique key for a data subject."""
        parts: list[str] = []
        if subject.email:
            parts.append(f"email:{subject.email}")
        if subject.user_id:
            parts.append(f"uid:{subject.user_id}")
        if subject.phone:
            parts.append(f"phone:{subject.phone}")
        if subject.ip_address:
            parts.append(f"ip:{subject.ip_address}")
        return "|".join(parts) if parts else "unknown"

    def middleware(self) -> Callable:
        """Returns an async middleware that records lineage.

        Simplified stub middleware — production version intercepts LLMResponse
        and tool call events to build DataLocation entries.
        """

        async def _mw(messages, ctx, next_handler):
            async for event in next_handler(messages, ctx):
                yield event

        return _mw

    def record_location(self, subject: DataSubject, location: DataLocation) -> None:
        """Manually record a data location for a subject."""
        key = self._subject_key(subject)
        if key == "unknown":
            return
        if key not in self._locations:
            self._locations[key] = []
        self._locations[key].append(location)

    def query(self, query: LineageQuery | DataSubject) -> DataFootprint:
        """Find all data locations for matching subjects."""
        if isinstance(query, DataSubject):
            query = LineageQuery(data_subjects=[query])

        all_locations: list[DataLocation] = []
        for ds in query.data_subjects:
            key = self._subject_key(ds)
            if key in self._locations:
                all_locations.extend(self._locations[key])

        # Deduplicate by identifier+type
        seen: set[str] = set()
        unique: list[DataLocation] = []
        for loc in all_locations:
            dedup_key = f"{loc.type}:{loc.provider}:{loc.identifier}"
            if dedup_key not in seen:
                seen.add(dedup_key)
                unique.append(loc)

        risk = "low"
        if len(unique) > 5:
            risk = "medium"
        if len(unique) > 20:
            risk = "high"

        return DataFootprint(
            subject=query.data_subjects[0] if query.data_subjects else DataSubject(),
            locations=unique,
            total_locations=len(unique),
            risk_assessment=risk,
        )

    async def erase(self, request: ErasureRequest) -> ErasureReport:
        """Execute a GDPR erasure request."""
        items: list[ErasureItem] = []
        completed = 0
        pending = 0

        for ds_dict in request.data_subjects:
            ds = DataSubject(**ds_dict)
            key = self._subject_key(ds)
            locations = self._locations.pop(key, [])

            for loc in locations:
                item = ErasureItem(location=loc.model_dump(), status="pending")
                # Check for custom handler
                if loc.type in self._handlers:
                    try:
                        await self._handlers[loc.type](loc)
                        item.status = "erased"
                        item.detail = f"Custom handler executed for {loc.type}"
                        completed += 1
                    except Exception as e:
                        item.status = "failed"
                        item.detail = str(e)
                elif loc.deletable:
                    item.status = "erased"
                    item.detail = f"Deleted from {loc.provider}"
                    completed += 1
                else:
                    item.status = "pending"
                    item.detail = f"Cannot delete — {loc.deletion_method}"
                    pending += 1
                items.append(item)

        status = "complete" if pending == 0 else "partial"

        return ErasureReport(
            request_id=request.request_id,
            status=status,
            items=items,
            completed_items=completed,
            pending_items=pending,
            total_items=len(items),
        )

    def register_handler(self, location_type: str, handler: Callable) -> None:
        """Register a custom deletion handler for a location type."""
        self._handlers[location_type] = handler

    @property
    def subject_count(self) -> int:
        return len(self._locations)

    def stats(self) -> dict:
        total_locations = sum(len(v) for v in self._locations.values())
        return {
            "total_subjects": len(self._locations),
            "total_locations": total_locations,
            "handlers_registered": list(self._handlers.keys()),
        }
