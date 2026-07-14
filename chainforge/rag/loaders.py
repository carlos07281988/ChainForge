"""Document loaders — load content from files into Documents."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from chainforge.rag.documents import Document


class TextLoader:
    """Load text files as documents.

    Args:
        path: File path.
        encoding: File encoding (default utf-8).
    """

    def __init__(self, path: str | Path, encoding: str = "utf-8"):
        self.path = Path(path)
        self.encoding = encoding

    def load(self) -> list[Document]:
        """Load the file as a single document."""
        if not self.path.exists():
            raise FileNotFoundError(f"File not found: {self.path}")
        text = self.path.read_text(encoding=self.encoding)
        return [
            Document(
                page_content=text,
                metadata={"source": str(self.path), "file_type": "text"},
            )
        ]


class CSVLoader:
    """Load CSV files as documents (one row per document).

    Args:
        path: File path.
        content_columns: Columns to include in page_content (None = all).
        metadata_columns: Columns to include as metadata.
    """

    def __init__(
        self,
        path: str | Path,
        content_columns: list[str] | None = None,
        metadata_columns: list[str] | None = None,
    ):
        self.path = Path(path)
        self.content_columns = content_columns
        self.metadata_columns = metadata_columns

    def load(self) -> list[Document]:
        if not self.path.exists():
            raise FileNotFoundError(f"File not found: {self.path}")
        documents = []
        with open(self.path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                content_cols = self.content_columns or list(row.keys())
                meta_cols = self.metadata_columns or []
                content = "\n".join(f"{k}: {row[k]}" for k in content_cols if k in row)
                metadata = {"source": str(self.path), "file_type": "csv"}
                for k in meta_cols:
                    if k in row:
                        metadata[k] = row[k]
                documents.append(Document(page_content=content, metadata=metadata))
        return documents


class JSONLoader:
    """Load JSON files as documents.

    Args:
        path: File path.
        content_key: Key for content (None = whole JSON as string).
        metadata_keys: Keys to include as metadata.
    """

    def __init__(
        self,
        path: str | Path,
        content_key: str | None = None,
        metadata_keys: list[str] | None = None,
    ):
        self.path = Path(path)
        self.content_key = content_key
        self.metadata_keys = metadata_keys or []

    def load(self) -> list[Document]:
        if not self.path.exists():
            raise FileNotFoundError(f"File not found: {self.path}")
        data = json.loads(self.path.read_text(encoding="utf-8"))
        # Handle both single object and array
        items = data if isinstance(data, list) else [data]
        documents = []
        for item in items:
            if self.content_key:
                content = str(item.get(self.content_key, ""))
            else:
                content = json.dumps(item, ensure_ascii=False)
            metadata = {"source": str(self.path), "file_type": "json"}
            for k in self.metadata_keys:
                if k in item:
                    metadata[k] = item[k]
            documents.append(Document(page_content=content, metadata=metadata))
        return documents
