# Copyright 2024 ChainForge Contributors
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
"""Text splitters — chunk documents for embedding and retrieval."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from chainforge.rag.documents import Document


class RecursiveCharacterTextSplitter(BaseModel):
    """Split text recursively by separators into chunks.

    Tries splitting by the first separator first, then recursively
    by subsequent separators if chunks are still too large.

    Args:
        chunk_size: Target chunk size in characters (default 1000).
        chunk_overlap: Overlap between chunks in characters (default 200).
        separators: Ordered list of separators to try.
    """

    chunk_size: int = Field(default=1000, ge=1)
    chunk_overlap: int = Field(default=200, ge=0)
    separators: list[str] = Field(default_factory=lambda: ["\n\n", "\n", ".", " ", ""])

    def split_text(self, text: str) -> list[str]:
        """Split text into chunks."""
        return self._split(text, list(self.separators))

    def split_documents(self, documents: list[Document]) -> list[Document]:
        """Split documents into smaller chunks, preserving metadata."""
        chunks = []
        for doc in documents:
            text_chunks = self.split_text(doc.page_content)
            for i, chunk in enumerate(text_chunks):
                meta = dict(doc.metadata)
                meta["chunk"] = i
                chunks.append(Document(page_content=chunk, metadata=meta))
        return chunks

    def _split(self, text: str, separators: list[str]) -> list[str]:
        """Split text into chunks using the available separators."""
        if not text:
            return []

        # Pick the first separator that appears in the text
        sep = separators[0] if separators else ""
        for s in separators:
            if s == "" or s in text:
                sep = s
                break

        # If empty separator, split into characters (last resort)
        if sep == "":
            # Simple chunk by chunk_size
            return [text[i:i + self.chunk_size] for i in range(0, len(text), self.chunk_size - self.chunk_overlap)]

        segments = text.split(sep)
        result = []
        current_chunk = []
        current_len = 0

        for seg in segments:
            seg_len = len(seg) + (len(sep) if current_chunk else 0)

            # If this segment alone exceeds chunk_size, split it with next separator
            if len(seg) >= self.chunk_size and len(separators) > 1:
                if current_chunk:
                    result.append(sep.join(current_chunk))
                    current_chunk = []
                    current_len = 0
                result.extend(self._split(seg, separators[1:]))
                continue

            if current_len + len(seg) + (len(sep) if current_chunk else 0) > self.chunk_size and current_chunk:
                result.append(sep.join(current_chunk))
                # Keep overlap: last few segments
                overlap = []
                ol = 0
                for cs in reversed(current_chunk):
                    if ol + len(cs) + (len(sep) if overlap else 0) <= self.chunk_overlap:
                        overlap.insert(0, cs)
                        ol += len(cs) + (len(sep) if len(overlap) > 1 else 0)
                    else:
                        break
                current_chunk = overlap
                current_len = ol

            current_chunk.append(seg)
            current_len += len(seg) + (len(sep) if len(current_chunk) > 1 else 0)

        if current_chunk:
            result.append(sep.join(current_chunk))

        return result


class TokenTextSplitter(BaseModel):
    """Split text by token count (approximate)."""

    chunk_size: int = Field(default=500, ge=1)
    chunk_overlap: int = Field(default=50, ge=0)

    def split_text(self, text: str) -> list[str]:
        """Split text into approximately equal token chunks.

        Uses ~4 chars per token heuristic.
        """
        approx_chars = self.chunk_size * 4
        overlap_chars = self.chunk_overlap * 4
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + approx_chars, len(text))
            # Try to break at a sentence boundary
            if end < len(text):
                # Find last sentence break
                break_at = max(
                    text.rfind(". ", start + approx_chars - 100, end),
                    text.rfind("\n", start + approx_chars - 100, end),
                    text.rfind(" ", start + approx_chars - 100, end),
                )
                if break_at > start:
                    end = break_at + 1
            chunks.append(text[start:end].strip())
            start = end - overlap_chars
        return [c for c in chunks if c]
