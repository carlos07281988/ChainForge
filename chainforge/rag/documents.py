"""Document abstraction for the RAG pipeline."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class Document(BaseModel):
    """A document chunk with content and metadata."""

    page_content: str = Field(description="Document text content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Source metadata")

    def __len__(self) -> int:
        return len(self.page_content)

    def __str__(self) -> str:
        return self.page_content[:200]


class DocumentLoader(Protocol):
    """Protocol for document loaders."""

    def load(self) -> list[Document]:
        """Load documents from a source.

        Returns:
            List of Document instances.
        """
        ...
