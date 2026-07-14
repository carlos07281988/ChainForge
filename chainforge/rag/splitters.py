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
        return self._split(text, self.separators)

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
        """Recursively split text."""
        final_chunks = []
        separator = separators[-1] if separators else ""
        _separators = separators[:]

        # Get the appropriate separator
        split_sep = _separators[-1] if _separators else ""
        for s in _separators:
            if s == "" or s in text:
                split_sep = s
                break

        if split_sep:
            splits = text.split(split_sep)
        else:
            splits = [text]

        # Good enough splitting
        good_splits = []
        for s in splits:
            if len(s) < self.chunk_size:
                good_splits.append(s)
            else:
                if good_splits:
                    merged = self._merge_splits(good_splits, split_sep)
                    final_chunks.extend(merged)
                    good_splits = []
                if len(_separators) > 1:
                    rest = self._split(s, _separators[1:])
                    final_chunks.extend(rest)
                else:
                    final_chunks.append(s)

        if good_splits:
            merged = self._merge_splits(good_splits, split_sep)
            final_chunks.extend(merged)

        return final_chunks

    def _merge_splits(self, splits: list[str], separator: str) -> list[str]:
        """Merge small splits into chunks of target size with overlap."""
        docs = []
        current = []
        total = 0
        for s in splits:
            _len = len(s)
            if total + _len >= self.chunk_size and current:
                docs.append(separator.join(current))
                # Keep overlap
                overlap_texts = []
                overlap_len = 0
                for cs in reversed(current):
                    if overlap_len + len(cs) < self.chunk_overlap:
                        overlap_texts.insert(0, cs)
                        overlap_len += len(cs)
                    else:
                        break
                current = overlap_texts
                total = overlap_len
            current.append(s)
            total += _len
        if current:
            docs.append(separator.join(current))
        return docs


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
