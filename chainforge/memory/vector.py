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
"""Vector memory — semantic retrieval over past conversations.

Provides:
  - VectorMemory: in-memory store with cosine similarity search
  - SQLiteVectorMemory: persistent store backed by SQLite
"""

from __future__ import annotations

import datetime
import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

import logging
from chainforge.logging import get_logger, log_data
from chainforge.memory.embedding import EmbeddingFunction, IdentityEmbedding, cosine_similarity

logger = get_logger("memory.vector")


@dataclass
class MemoryEntry:
    """A single entry in the vector memory store."""

    id: str
    text: str
    embedding: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()


class VectorMemory(BaseModel):
    """In-memory semantic memory that stores and retrieves via vector similarity.

    Usage:
        memory = VectorMemory(embedding_fn=IdentityEmbedding(dim=64))
        await memory.add("The user likes Python")
        results = await memory.query("What language does the user prefer?")
    """

    embedding_fn: Any = Field(default_factory=lambda: IdentityEmbedding(dim=64))
    store: list = Field(default_factory=list, description="In-memory entry store")

    model_config = {"arbitrary_types_allowed": True}

    @property
    def dim(self) -> int:
        return self.embedding_fn.dim

    async def add(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
        *,
        embedding: list[float] | None = None,
    ) -> str:
        if embedding is None:
            results = await self.embedding_fn.embed([text])
            embedding = results[0]
        entry_id = str(uuid.uuid4())
        entry = MemoryEntry(
            id=entry_id,
            text=text,
            embedding=embedding,
            metadata=metadata or {},
        )
        self.store.append(entry)
        log_data(logger, logging.DEBUG, f"Stored entry {entry_id}", data={"text_len": len(text)})
        return entry_id

    async def add_many(
        self,
        items: list[tuple[str, dict[str, Any] | None]],
    ) -> list[str]:
        texts = [item[0] for item in items]
        embeddings = await self.embedding_fn.embed(texts)
        ids = []
        for (text, metadata), emb in zip(items, embeddings):
            entry = MemoryEntry(
                id=str(uuid.uuid4()),
                text=text,
                embedding=emb,
                metadata=metadata or {},
            )
            self.store.append(entry)
            ids.append(entry.id)
        return ids

    async def query(
        self,
        text: str,
        k: int = 5,
        min_score: float = 0.0,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if not self.store:
            return []
        query_emb = (await self.embedding_fn.embed([text]))[0]
        scored = []
        for entry in self.store:
            if filter_metadata:
                if not all(entry.metadata.get(k) == v for k, v in filter_metadata.items()):
                    continue
            score = cosine_similarity(query_emb, entry.embedding)
            if score >= min_score:
                scored.append((score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"id": entry.id, "text": entry.text, "metadata": entry.metadata,
             "timestamp": entry.timestamp, "score": round(score, 4)}
            for score, entry in scored[:k]
        ]

    async def remove(self, entry_id: str) -> bool:
        for i, entry in enumerate(self.store):
            if entry.id == entry_id:
                self.store.pop(i)
                return True
        return False

    async def clear(self) -> None:
        self.store.clear()

    @property
    def size(self) -> int:
        return len(self.store)

    def stats(self) -> dict[str, Any]:
        return {"size": self.size, "dim": self.dim, "type": type(self.embedding_fn).__name__}


# ── SQLite-backed Vector Memory ──────────────────────────────────────────


class SQLiteVectorMemory(BaseModel):
    """Persistent vector memory backed by SQLite.

    Stores entries in a SQLite database with JSON metadata.
    Embeddings are stored as JSON arrays for simplicity (no vector extension needed).

    For production, consider using sqlite-vec or a dedicated vector DB.

    Usage:
        memory = SQLiteVectorMemory("memory.db", embedding_fn=my_embedder)
        await memory.add("The user likes Python")
        results = await memory.query("What language?")
    """

    db_path: str = Field(default="chainforge_memory.db")
    embedding_fn: Any = Field(default_factory=lambda: IdentityEmbedding(dim=64))
    table_name: str = Field(default="memory_entries")

    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, **data):
        super().__init__(**data)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                embedding TEXT NOT NULL,
                metadata TEXT DEFAULT '{{}}',
                timestamp TEXT NOT NULL
            )
        """)
        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{self.table_name}_ts
            ON {self.table_name}(timestamp)
        """)
        conn.commit()
        conn.close()

    @property
    def dim(self) -> int:
        return self.embedding_fn.dim

    async def add(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
        *,
        embedding: list[float] | None = None,
    ) -> str:
        if embedding is None:
            results = await self.embedding_fn.embed([text])
            embedding = results[0]
        entry_id = str(uuid.uuid4())
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn = self._get_conn()
        conn.execute(
            f"INSERT OR REPLACE INTO {self.table_name} (id, text, embedding, metadata, timestamp) VALUES (?, ?, ?, ?, ?)",
            (entry_id, text, json.dumps(embedding), json.dumps(metadata or {}), ts),
        )
        conn.commit()
        conn.close()
        return entry_id

    async def add_many(
        self,
        items: list[tuple[str, dict[str, Any] | None]],
    ) -> list[str]:
        texts = [item[0] for item in items]
        embeddings = await self.embedding_fn.embed(texts)
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn = self._get_conn()
        ids = []
        for (text, metadata), emb in zip(items, embeddings):
            entry_id = str(uuid.uuid4())
            conn.execute(
                f"INSERT INTO {self.table_name} (id, text, embedding, metadata, timestamp) VALUES (?, ?, ?, ?, ?)",
                (entry_id, text, json.dumps(emb), json.dumps(metadata or {}), ts),
            )
            ids.append(entry_id)
        conn.commit()
        conn.close()
        return ids

    async def query(
        self,
        text: str,
        k: int = 5,
        min_score: float = 0.0,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        query_emb = (await self.embedding_fn.embed([text]))[0]
        conn = self._get_conn()
        rows = conn.execute(
            f"SELECT id, text, embedding, metadata, timestamp FROM {self.table_name}"
        ).fetchall()
        conn.close()

        scored = []
        for row in rows:
            entry_emb = json.loads(row["embedding"])
            entry_meta = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else {}

            if filter_metadata:
                if not all(entry_meta.get(k) == v for k, v in filter_metadata.items()):
                    continue

            score = cosine_similarity(query_emb, entry_emb)
            if score >= min_score:
                scored.append((score, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "id": row["id"],
                "text": row["text"],
                "metadata": json.loads(row["metadata"]) if isinstance(row["metadata"], str) else {},
                "timestamp": row["timestamp"],
                "score": round(score, 4),
            }
            for score, row in scored[:k]
        ]

    async def remove(self, entry_id: str) -> bool:
        conn = self._get_conn()
        cur = conn.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (entry_id,))
        conn.commit()
        affected = cur.rowcount
        conn.close()
        return affected > 0

    async def clear(self) -> None:
        conn = self._get_conn()
        conn.execute(f"DELETE FROM {self.table_name}")
        conn.commit()
        conn.close()

    @property
    def size(self) -> int:
        conn = self._get_conn()
        row = conn.execute(f"SELECT COUNT(*) AS cnt FROM {self.table_name}").fetchone()
        conn.close()
        return row["cnt"] if row else 0

    def stats(self) -> dict[str, Any]:
        return {"size": self.size, "dim": self.dim, "type": "SQLiteVectorMemory", "db_path": self.db_path}
