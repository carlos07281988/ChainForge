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


class DirectoryLoader:
    """Load all files in a directory as documents."""

    def __init__(self, path, glob_pattern="*", loader_map=None, recursive=False):
        from pathlib import Path
        self.path = Path(path)
        self.glob_pattern = glob_pattern
        self.loader_map = loader_map or {}
        self.recursive = recursive

    def load(self) -> list:
        if not self.path.exists() or not self.path.is_dir():
            raise FileNotFoundError(f"Directory not found: {self.path}")
        from pathlib import Path as P
        pattern = "**/*" if self.recursive else "*"
        all_docs = []
        for file_path in P(self.path).glob(pattern):
            if file_path.is_file() and file_path.match(self.glob_pattern):
                ext = file_path.suffix.lower()
                loader_cls = self.loader_map.get(ext, TextLoader)
                try:
                    loader = loader_cls(str(file_path))
                    docs = loader.load()
                    all_docs.extend(docs)
                except Exception as e:
                    import logging
                    logging.warning(f"Failed to load {file_path}: {e}")
        return all_docs


class HTMLLoader:
    """Load HTML files, extracting text content."""

    def __init__(self, path, extract_text=True):
        from pathlib import Path
        self.path = Path(path)
        self.extract_text = extract_text

    def load(self) -> list:
        if not self.path.exists():
            raise FileNotFoundError(f"File not found: {self.path}")
        raw = self.path.read_text(encoding="utf-8")
        content = raw
        if self.extract_text:
            import re
            content = re.sub(r"<[^>]+>", " ", raw)
            content = re.sub(r"\s+", " ", content).strip()
        from chainforge.rag.documents import Document
        return [
            Document(
                page_content=content,
                metadata={"source": str(self.path), "file_type": "html"},
            )
        ]
