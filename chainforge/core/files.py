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
"""File handling utilities — load images, PDFs, CSVs into Message parts."""

from __future__ import annotations

import base64
import csv
import io
import json
import mimetypes
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from chainforge.logging import get_logger

logger = get_logger("core.files")


# ── Supported file types ──────────────────────────────────────────────────

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}
TEXT_EXTENSIONS = {".txt", ".md", ".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".yaml", ".yml", ".csv"}
DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".xlsx"}


class FileContent:
    """Represents a loaded file with metadata."""

    def __init__(
        self,
        data: bytes,
        mime_type: str,
        filename: str = "",
        text: str | None = None,
    ):
        self.data = data
        self.mime_type = mime_type
        self.filename = filename
        self.text = text

    @property
    def base64(self) -> str:
        return base64.b64encode(self.data).decode("utf-8")

    @property
    def is_image(self) -> bool:
        return self.mime_type.startswith("image/")

    def __repr__(self) -> str:
        return f"FileContent(name={self.filename}, type={self.mime_type}, size={len(self.data)}b)"


class FileLoader:
    """Load and analyze files from the local filesystem.

    Usage:
        loader = FileLoader()
        fc = loader.load("image.png")
        print(fc.is_image, fc.mime_type)
    """

    def load(self, path: str | os.PathLike) -> FileContent:
        """Load a file from disk.

        Args:
            path: Path to the file.

        Returns:
            FileContent with data and metadata.

        Raises:
            FileNotFoundError: File does not exist.
            ValueError: Unsupported or unreadable file.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        data = path.read_bytes()
        mime_type, _ = mimetypes.guess_type(str(path))
        ext = path.suffix.lower()
        if mime_type is None:
            mime_type = {
                ".md": "text/markdown",
                ".yaml": "application/x-yaml",
                ".yml": "application/x-yaml",
            }.get(ext, "application/octet-stream")

        text = None
        if mime_type.startswith("text/") or ext in TEXT_EXTENSIONS:
            text = data.decode("utf-8", errors="replace")

        return FileContent(data=data, mime_type=mime_type, filename=path.name, text=text)

    def load_image_as_b64(self, path: str | os.PathLike) -> str:
        """Load an image file and return its base64-encoded data URI.

        Args:
            path: Path to the image file.

        Returns:
            Data URI string suitable for LLM vision APIs.
        """
        fc = self.load(path)
        if not fc.is_image:
            raise ValueError(f"Not an image: {path} ({fc.mime_type})")
        return f"data:{fc.mime_type};base64,{fc.base64}"

    def load_text(self, path: str | os.PathLike) -> str:
        """Load a text file.

        Args:
            path: Path to the text file.

        Returns:
            File content as string.
        """
        fc = self.load(path)
        if fc.text is None:
            return fc.data.decode("utf-8", errors="replace")
        return fc.text

    def load_csv(self, path: str | os.PathLike) -> list[dict[str, str]]:
        """Load a CSV file and return rows as dicts.

        Args:
            path: Path to the CSV file.

        Returns:
            List of {column: value} dicts.
        """
        text = self.load_text(path)
        reader = csv.DictReader(io.StringIO(text))
        return list(reader)

    def load_json(self, path: str | os.PathLike) -> Any:
        """Load a JSON file.

        Args:
            path: Path to the JSON file.

        Returns:
            Parsed JSON data.
        """
        text = self.load_text(path)
        return json.loads(text)

    def detect(self, path: str | os.PathLike) -> str:
        """Detect the type of a file.

        Returns:
            One of: "image", "text", "document", "data", "unknown".
        """
        ext = Path(path).suffix.lower()
        if ext in IMAGE_EXTENSIONS:
            return "image"
        if ext in DOCUMENT_EXTENSIONS:
            return "document"
        if ext in {".json", ".csv", ".xml", ".yaml", ".yml"}:
            return "data"
        if ext in TEXT_EXTENSIONS:
            return "text"
        return "unknown"


# ── Convenience functions ──────────────────────────────────────────────────


def load_file(path: str | os.PathLike) -> FileContent:
    """Quick-load a file.

    Example:
        fc = load_file("chart.png")
        if fc.is_image:
            print(f"Loaded image: {fc.filename} ({len(fc.data)} bytes)")
    """
    return FileLoader().load(path)


def load_image(path: str | os.PathLike) -> str:
    """Quick-load an image as base64 data URI."""
    return FileLoader().load_image_as_b64(path)
