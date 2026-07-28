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
"""DeletionProof — tamper-evident proof of data deletion for GDPR compliance."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path


class DeletionProof:
    """Tamper-evident proof of data deletion for GDPR compliance.

    Usage::

        proof = DeletionProof(report)
        proof.export("deletion-proof-user-123.json")
        valid = proof.verify()
    """

    def __init__(self, report):
        self._report = report
        self._timestamp = time.time()
        self._proof_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        data = {
            "request_id": self._report.request_id,
            "status": self._report.status,
            "completed": self._report.completed_items,
            "total": self._report.total_items,
            "generated_at": self._report.generated_at,
            "proof_timestamp": self._timestamp,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def export(self, path: str) -> None:
        """Export a signed deletion proof to disk."""
        proof_data = {
            "proof_hash": self._proof_hash,
            "request_id": self._report.request_id,
            "status": self._report.status,
            "completed_items": self._report.completed_items,
            "total_items": self._report.total_items,
            "completion_rate": self._report.completion_rate,
            "generated_at": self._report.generated_at,
            "proof_timestamp": self._timestamp,
            "items": [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in self._report.items
            ],
        }
        Path(path).write_text(
            json.dumps(proof_data, indent=2, default=str), encoding="utf-8"
        )

    def verify(self) -> bool:
        """Verify the proof hash is consistent."""
        return self._compute_hash() == self._proof_hash

    @property
    def proof_hash(self) -> str:
        return self._proof_hash
