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
"""ModelVersionTracker — record and verify model versions for reproducibility.

Captures a snapshot of (provider, model, params) on each call so that
every inference can be reproduced or audited later.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from pydantic import BaseModel, Field


def _make_hash(*parts: str) -> str:
    """Create a short deterministic hash from string parts."""
    combined = "|".join(parts)
    return hashlib.sha256(combined.encode()).hexdigest()[:12]


class VersionRecord(BaseModel):
    """A single version snapshot of a model call.

    Attributes:
        record_id: Unique record identifier.
        timestamp: Unix timestamp when the snapshot was taken.
        provider: Provider name (e.g. "nim", "openai").
        model: Model identifier (e.g. "meta/llama-3.1-70b-instruct").
        model_version: Optional server-reported version string.
        params_hash: Hash of the generation parameters.
        params: The actual parameters used (for audit).
        extra: Arbitrary metadata (node, user, session).
    """

    record_id: str = Field(default_factory=lambda: _make_hash(str(time.time())))
    timestamp: float = Field(default_factory=time.time)
    provider: str = Field(description="Provider name")
    model: str = Field(description="Model identifier")
    model_version: str | None = Field(default=None,
                                       description="Server-reported version")
    params_hash: str = Field(description="Hash of generation parameters")
    params: dict[str, Any] = Field(default_factory=dict,
                                    description="Generation parameters")
    extra: dict[str, Any] = Field(default_factory=dict,
                                   description="Additional metadata")


class ModelVersionTracker:
    """Records model version snapshots and verifies consistency.

    Usage:
        tracker = ModelVersionTracker()

        record = tracker.snapshot("nim", "meta/llama-3.1-70b-instruct",
                                  temperature=0.7, top_p=0.9)

        is_consistent = tracker.verify("nim", record.params_hash)
    """

    def __init__(self):
        self._records: dict[str, VersionRecord] = {}

    def snapshot(
        self,
        provider: str,
        model: str,
        model_version: str | None = None,
        **params: Any,
    ) -> VersionRecord:
        """Record a version snapshot of a model call.

        Args:
            provider: Provider name.
            model: Model identifier.
            model_version: Optional server-reported version.
            **params: Generation parameters to hash.

        Returns:
            VersionRecord with hash for later verification.
        """
        params_hash = _make_hash(
            provider,
            model,
            json.dumps(params, sort_keys=True, default=str),
        )

        record = VersionRecord(
            provider=provider,
            model=model,
            model_version=model_version,
            params_hash=params_hash,
            params=dict(params),
            extra={"version_snapshot_at": time.time()},
        )

        self._records[record.record_id] = record
        return record

    def verify(
        self,
        provider: str,
        expected_params_hash: str,
        current_params: dict[str, Any] | None = None,
    ) -> bool:
        """Verify the current model state matches the expected snapshot.

        Args:
            provider: Provider name to check.
            expected_params_hash: Hash from a previous snapshot.
            current_params: Current parameters (optional). If provided,
                           hashes them and compares to expected.

        Returns:
            True if the current state matches the expected snapshot.
        """
        if current_params is not None:
            model = current_params.pop("model", "unknown")
            current_hash = _make_hash(
                provider,
                model,
                json.dumps(current_params, sort_keys=True, default=str),
            )
            return current_hash == expected_params_hash

        for record in self._records.values():
            if (record.provider == provider and
                    record.params_hash == expected_params_hash):
                return True
        return False

    def get_record(self, record_id: str) -> VersionRecord | None:
        """Retrieve a specific version record by ID."""
        return self._records.get(record_id)

    def list_records(self, provider: str | None = None) -> list[VersionRecord]:
        """List all records, optionally filtered by provider."""
        records = list(self._records.values())
        if provider:
            records = [r for r in records if r.provider == provider]
        return sorted(records, key=lambda r: r.timestamp, reverse=True)

    def clear(self) -> None:
        """Remove all records."""
        self._records.clear()

    @property
    def record_count(self) -> int:
        return len(self._records)
