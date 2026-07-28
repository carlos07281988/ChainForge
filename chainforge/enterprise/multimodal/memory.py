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
"""MultiModalMemory -- persistent storage for multi-modal agent interactions."""

from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InteractionRecord(BaseModel):
    """A single multi-modal interaction record."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, description="Unique interaction ID")
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp of the interaction")
    text_content: str | None = Field(default=None, description="Text content of the interaction")
    image_paths: list[str] = Field(default_factory=list, description="Image file paths referenced")
    audio_paths: list[str] = Field(default_factory=list, description="Audio file paths referenced")
    model_used: str | None = Field(default=None, description="Model that handled the interaction")
    response_text: str | None = Field(default=None, description="Agent response text")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary extra metadata")


class MultiModalMemory(BaseModel):
    """In-memory and optionally persistent store for multi-modal interactions.

    Stores text, image, and audio interactions with configurable filters.
    Supports searching by query text and modality type.

    Usage::

        memory = MultiModalMemory(store_images=True, store_audio=True)
        memory.add(interaction)
        results = memory.search("dog picture", modality_filter="image")
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    store_text: bool = Field(default=True, description="Store text interactions")
    store_images: bool = Field(default=True, description="Store image interactions")
    store_audio: bool = Field(default=True, description="Store audio interactions")
    max_records: int = Field(default=10_000, description="Maximum records to keep in memory")

    _records: list[InteractionRecord] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, interaction: InteractionRecord) -> None:
        """Store a multi-modal interaction record.

        Respects the ``store_text``, ``store_images``, and ``store_audio``
        flags — an interaction containing only images will be skipped if
        ``store_images=False``.
        """
        has_text = bool(interaction.text_content)
        has_images = bool(interaction.image_paths)
        has_audio = bool(interaction.audio_paths)

        # Honour storage flags
        if has_text and not self.store_text:
            return
        if has_images and not self.store_images:
            return
        if has_audio and not self.store_audio:
            return

        self._records.append(interaction)
        self._prune()

    def search(
        self, query: str = "", modality_filter: str | None = None
    ) -> list[InteractionRecord]:
        """Search stored interactions.

        Parameters
        ----------
        query:
            Case-insensitive substring match against ``text_content`` and ``response_text``.
        modality_filter:
            If ``"image"``, only return interactions with image_paths.
            If ``"audio"``, only return interactions with audio_paths.
            If ``"text"``, only return interactions with text_content.
            If ``None``, return all matching.
        """
        results: list[InteractionRecord] = []

        q = query.lower()
        for record in self._records:
            # Modality filter
            if modality_filter:
                if modality_filter == "image" and not record.image_paths:
                    continue
                if modality_filter == "audio" and not record.audio_paths:
                    continue
                if modality_filter == "text" and not record.text_content:
                    continue

            # Text search (empty query matches all)
            if q:
                text_match = q in (record.text_content or "").lower()
                resp_match = q in (record.response_text or "").lower()
                if not text_match and not resp_match:
                    continue

            results.append(record)

        return results

    def clear(self) -> None:
        """Remove all stored records."""
        self._records.clear()

    def count(self) -> int:
        """Return the number of stored records."""
        return len(self._records)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _prune(self) -> None:
        """Discard oldest records when exceeding ``max_records``."""
        over = len(self._records) - self.max_records
        if over > 0:
            self._records = self._records[over:]
