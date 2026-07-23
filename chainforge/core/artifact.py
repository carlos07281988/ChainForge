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
"""Artifact Management — first-class file/media artifacts for agent execution.

Inspired by Google ADK's rich media artifact system. Artifacts are named
data blobs (files, images, audio, structured data) produced or consumed
during agent execution. They can be referenced by name across turns,
persisted to disk, and queried by metadata.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ArtifactType(str, Enum):
    """Types of artifacts an agent can produce or consume."""
    text = "text"
    code = "code"
    image = "image"
    audio = "audio"
    video = "video"
    file = "file"
    data = "data"
    document = "document"
    unknown = "unknown"


class Artifact(BaseModel):
    """A named data blob produced or consumed during agent execution."""

    id: str = Field(default_factory=lambda: f"art_{uuid.uuid4().hex[:12]}")
    name: str = Field(description="Human-readable name (e.g. 'chart.png')")
    data: bytes = Field(description="Raw artifact data", repr=False)
    mime_type: str = Field(default="application/octet-stream")
    artifact_type: ArtifactType = Field(default=ArtifactType.unknown)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    size: int = Field(default=0)

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if self.size == 0 and self.data:
            object.__setattr__(self, "size", len(self.data))
        if self.artifact_type == ArtifactType.unknown and self.mime_type:
            object.__setattr__(self, "artifact_type", self._detect_type())

    def _detect_type(self) -> ArtifactType:
        mt = self.mime_type.lower()
        if mt.startswith("text/"):
            if self.name.endswith((".py", ".js", ".ts", ".java", ".rs", ".go", ".c", ".cpp")):
                return ArtifactType.code
            return ArtifactType.text
        if mt.startswith("image/"):
            return ArtifactType.image
        if mt.startswith("audio/"):
            return ArtifactType.audio
        if mt.startswith("video/"):
            return ArtifactType.video
        if mt in ("application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"):
            return ArtifactType.document
        if mt in ("application/json", "text/csv", "application/xml", "application/x-yaml"):
            return ArtifactType.data
        if mt == "application/octet-stream":
            ext = Path(self.name).suffix.lower() if self.name else ""
            if ext in (".py", ".js", ".ts", ".rs", ".go", ".sh"):
                return ArtifactType.code
        return ArtifactType.file

    @property
    def base64_data(self) -> str:
        return base64.b64encode(self.data).decode("utf-8")

    @property
    def data_uri(self) -> str:
        return f"data:{self.mime_type};base64,{self.base64_data}"

    @property
    def text(self) -> str | None:
        try:
            return self.data.decode("utf-8")
        except UnicodeDecodeError:
            return None

    def to_message_part(self) -> dict[str, Any]:
        """Convert to an OpenAI-compatible content part for multi-modal messages."""
        if self.artifact_type == ArtifactType.image:
            return {"type": "image_url", "image_url": {"url": self.data_uri}}
        return {"type": "text", "text": self.text or f"[Artifact: {self.name} ({self.mime_type})]"}

    def write_to(self, path: str | Path) -> Path:
        path = Path(path)
        path.write_bytes(self.data)
        return path

    @classmethod
    def from_file(cls, path: str | Path, name: str | None = None,
                  metadata: dict[str, Any] | None = None) -> "Artifact":
        path = Path(path)
        data = path.read_bytes()
        mime, _ = mimetypes.guess_type(str(path))
        return cls(
            name=name or path.name, data=data,
            mime_type=mime or "application/octet-stream",
            metadata=metadata or {},
        )

    @classmethod
    def from_text(cls, text: str, name: str = "text.txt",
                  mime_type: str = "text/plain",
                  metadata: dict[str, Any] | None = None) -> "Artifact":
        return cls(name=name, data=text.encode("utf-8"),
                   mime_type=mime_type, metadata=metadata or {})

    @classmethod
    def from_data(cls, data: dict[str, Any] | list[dict[str, Any]],
                  name: str = "data.json",
                  metadata: dict[str, Any] | None = None) -> "Artifact":
        return cls(name=name,
                   data=json.dumps(data, indent=2, default=str).encode("utf-8"),
                   mime_type="application/json", metadata=metadata or {})


class _ArtifactEntry(BaseModel):
    artifact: Artifact = Field(description="The stored artifact")
    access_count: int = Field(default=0)
    last_accessed: float | None = Field(default=None)


class ArtifactStore(BaseModel):
    """Store and manage artifacts produced during agent execution.

    Provides artifact lifecycle management: save, retrieve, search, prune.
    Can be scoped to a session or shared globally.

    Usage:
        store = ArtifactStore()
        art = await store.save("analysis.py", data=b"print('hello')", mime_type="text/x-python")
        loaded = await store.get(art.id)
        results = await store.search(tags=["code"])
        await store.prune(max_age=3600)
    """

    model_config = {"arbitrary_types_allowed": True}

    name: str = Field(default="default")
    max_artifacts: int = Field(default=1000)
    persist_dir: str | None = Field(default=None)

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self._entries: dict[str, _ArtifactEntry] = {}
        self._name_index: dict[str, list[str]] = {}

    async def save(self, name: str, data: bytes, *,
                   mime_type: str = "application/octet-stream",
                   artifact_type: ArtifactType | None = None,
                   metadata: dict[str, Any] | None = None,
                   artifact_id: str | None = None) -> Artifact:
        """Save a new artifact to the store."""
        art = Artifact(
            id=artifact_id or f"art_{uuid.uuid4().hex[:12]}",
            name=name, data=data, mime_type=mime_type,
            artifact_type=artifact_type or ArtifactType.unknown,
            metadata=metadata or {},
        )
        self._entries[art.id] = _ArtifactEntry(artifact=art)
        self._name_index.setdefault(name, []).append(art.id)
        if len(self._entries) > self.max_artifacts:
            await self._prune_oldest()
        return art

    async def save_text(self, name: str, text: str, *,
                        mime_type: str = "text/plain",
                        metadata: dict[str, Any] | None = None) -> Artifact:
        return await self.save(name, text.encode("utf-8"),
                               mime_type=mime_type, metadata=metadata)

    async def save_json(self, name: str, data: dict[str, Any] | list[dict[str, Any]], *,
                        metadata: dict[str, Any] | None = None) -> Artifact:
        return await self.save(
            name, json.dumps(data, indent=2, default=str).encode("utf-8"),
            mime_type="application/json", metadata=metadata,
        )

    async def save_from_file(self, path: str | Path, *,
                             name: str | None = None,
                             metadata: dict[str, Any] | None = None) -> Artifact:
        path = Path(path)
        data = path.read_bytes()
        mime, _ = mimetypes.guess_type(str(path))
        return await self.save(name or path.name, data,
                               mime_type=mime or "application/octet-stream",
                               metadata=metadata)

    async def get(self, artifact_id: str) -> Artifact | None:
        entry = self._entries.get(artifact_id)
        if entry is None:
            return None
        entry.access_count += 1
        entry.last_accessed = time.time()
        return entry.artifact

    async def delete(self, artifact_id: str) -> bool:
        entry = self._entries.pop(artifact_id, None)
        if entry is None:
            return False
        try:
            self._name_index.get(entry.artifact.name, []).remove(artifact_id)
        except ValueError:
            pass
        return True

    async def list(self) -> list[Artifact]:
        entries = sorted(self._entries.values(),
                         key=lambda e: e.artifact.created_at, reverse=True)
        return [e.artifact for e in entries]

    async def search(self, *, name: str | None = None,
                     tags: list[str] | None = None,
                     artifact_type: ArtifactType | None = None,
                     mime_type: str | None = None,
                     limit: int = 20) -> list[Artifact]:
        """Search artifacts by name, tags, type, or MIME type."""
        results: list[Artifact] = []
        for entry in self._entries.values():
            art = entry.artifact
            if name and name.lower() not in art.name.lower():
                continue
            if tags:
                art_tags = art.metadata.get("tags", [])
                if not any(t in art_tags for t in tags):
                    continue
            if artifact_type and art.artifact_type != artifact_type:
                continue
            if mime_type and not art.mime_type.startswith(mime_type):
                continue
            results.append(art)
            if len(results) >= limit:
                break
        results.sort(key=lambda a: a.created_at, reverse=True)
        return results

    async def get_by_name(self, name: str) -> Artifact | None:
        ids = self._name_index.get(name, [])
        if not ids:
            return None
        latest_id = max(ids, key=lambda i: self._entries[i].artifact.created_at)
        return await self.get(latest_id)

    def session_scope(self, session_id: str) -> "ScopedArtifactStore":
        return ScopedArtifactStore(store=self, key="session_id", value=session_id)

    async def prune(self, *, max_age: float | None = None,
                    max_count: int | None = None) -> int:
        removed = 0
        now = time.time()
        if max_age is not None:
            to_remove = [
                aid for aid, entry in self._entries.items()
                if now - entry.artifact.created_at > max_age
            ]
            for aid in to_remove:
                await self.delete(aid)
                removed += 1
        if max_count is not None and len(self._entries) > max_count:
            sorted_entries = sorted(
                self._entries.items(),
                key=lambda x: x[1].artifact.created_at,
            )
            for aid, _ in sorted_entries[:len(self._entries) - max_count]:
                await self.delete(aid)
                removed += 1
        return removed

    def clear(self) -> None:
        self._entries.clear()
        self._name_index.clear()

    @property
    def count(self) -> int:
        return len(self._entries)

    @property
    def total_size(self) -> int:
        return sum(len(e.artifact.data) for e in self._entries.values())

    def stats(self) -> dict[str, Any]:
        type_counts: dict[str, int] = {}
        for entry in self._entries.values():
            t = entry.artifact.artifact_type.value
            type_counts[t] = type_counts.get(t, 0) + 1
        return {
            "name": self.name, "count": self.count,
            "total_size": self.total_size, "by_type": type_counts,
        }

    async def _prune_oldest(self) -> None:
        overflow = len(self._entries) - self.max_artifacts
        if overflow <= 0:
            return
        sorted_entries = sorted(
            self._entries.items(),
            key=lambda x: x[1].artifact.created_at,
        )
        for i in range(overflow):
            await self.delete(sorted_entries[i][0])


class ScopedArtifactStore:
    """A view into an ArtifactStore filtered by a metadata key-value pair."""

    def __init__(self, store: ArtifactStore, key: str, value: str):
        self._store = store
        self._key = key
        self._value = value

    async def save(self, name: str, data: bytes, **kwargs: Any) -> Artifact:
        kwargs.setdefault("metadata", {})
        kwargs["metadata"][self._key] = self._value
        return await self._store.save(name, data, **kwargs)

    async def get(self, artifact_id: str) -> Artifact | None:
        art = await self._store.get(artifact_id)
        return art if (art and art.metadata.get(self._key) == self._value) else None

    async def list(self) -> list[Artifact]:
        return [a for a in await self._store.list()
                if a.metadata.get(self._key) == self._value]

    @property
    def count(self) -> int:
        return len([a for a in self._store._entries.values()
                    if a.artifact.metadata.get(self._key) == self._value])
