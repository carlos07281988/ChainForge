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


# ── PDF Loader ────────────────────────────────────────────────────────────


class PDFLoader:
    """Load PDF files as documents with text extraction.

    Requires the ``pypdf`` or ``pdfminer.six`` package.
    Falls back to ``pdftotext`` command-line tool if available.

    Usage:
        loader = PDFLoader("report.pdf")
        docs = loader.load()
    """

    def __init__(self, path: str | Path):
        from pathlib import Path
        self.path = Path(path)

    def load(self) -> list[Document]:
        if not self.path.exists():
            raise FileNotFoundError(f"File not found: {self.path}")

        text = ""
        try:
            import pypdf
            reader = pypdf.PdfReader(str(self.path))
            for page in reader.pages:
                text += page.extract_text() or ""
                text += "\n\n"
        except ImportError:
            try:
                from pdfminer.high_level import extract_text
                text = extract_text(str(self.path))
            except ImportError:
                try:
                    import subprocess
                    result = subprocess.run(
                        ["pdftotext", str(self.path), "-"],
                        capture_output=True, text=True, timeout=30,
                    )
                    text = result.stdout
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    raise ImportError(
                        "PDFLoader requires pypdf or pdfminer.six. "
                        "Install: pip install pypdf"
                    )

        return [
            Document(
                page_content=text.strip(),
                metadata={"source": str(self.path), "file_type": "pdf"},
            )
        ]


# ── Notion Loader ─────────────────────────────────────────────────────────


class NotionLoader:
    """Load Notion pages and databases as documents.

    Requires the ``notion-client`` package and NOTION_TOKEN environment variable.
    Uses the Notion API to fetch page content and database entries.

    Usage:
        loader = NotionLoader(page_id="abc123")
        docs = loader.load()
    """

    def __init__(
        self,
        page_id: str | None = None,
        database_id: str | None = None,
        notion_token: str | None = None,
    ):
        self.page_id = page_id
        self.database_id = database_id
        self._token = notion_token

    def _get_client(self):
        import os
        from notion_client import Client
        return Client(auth=self._token or os.environ.get("NOTION_TOKEN", ""))

    def _extract_text(self, block) -> str:
        """Extract text from a Notion block."""
        block_type = block.get("type", "")
        if block_type == "child_page":
            return block.get("child_page", {}).get("title", "")
        content = block.get(block_type, {})
        if "rich_text" in content:
            return "".join(
                t.get("plain_text", "") for t in content["rich_text"]
            )
        return ""

    def load(self) -> list[Document]:
        client = self._get_client()
        documents = []

        if self.page_id:
            # Fetch page content
            page = client.pages.retrieve(page_id=self.page_id)
            title = "Untitled"
            if "properties" in page and "title" in page["properties"]:
                title_parts = page["properties"]["title"].get("title", [])
                if title_parts:
                    title = "".join(t.get("plain_text", "") for t in title_parts)

            blocks = client.blocks.children.list(block_id=self.page_id)
            text_parts = [f"# {title}"]
            for block in blocks.get("results", []):
                text = self._extract_text(block)
                if text:
                    text_parts.append(text)

            documents.append(Document(
                page_content="\n\n".join(text_parts),
                metadata={"source": f"notion://{self.page_id}", "file_type": "notion", "title": title},
            ))

        if self.database_id:
            # Fetch database entries
            results = client.databases.query(database_id=self.database_id)
            for page in results.get("results", []):
                props = page.get("properties", {})
                text_parts = []
                meta = {"source": f"notion://db/{self.database_id}", "file_type": "notion"}
                for prop_name, prop_value in props.items():
                    prop_type = prop_value.get("type", "")
                    if prop_type == "title" and prop_value.get("title"):
                        title_text = "".join(t.get("plain_text", "") for t in prop_value["title"])
                        text_parts.append(f"# {title_text}")
                        meta["title"] = title_text
                    elif prop_type == "rich_text" and prop_value.get("rich_text"):
                        text_parts.append(
                            "".join(t.get("plain_text", "") for t in prop_value["rich_text"])
                        )
                    elif prop_type == "select" and prop_value.get("select"):
                        text_parts.append(f"{prop_name}: {prop_value['select'].get('name', '')}")
                    elif prop_type == "multi_select" and prop_value.get("multi_select"):
                        names = [s.get("name", "") for s in prop_value["multi_select"]]
                        text_parts.append(f"{prop_name}: {', '.join(names)}")

                if text_parts:
                    documents.append(Document(
                        page_content="\n".join(text_parts),
                        metadata=meta,
                    ))

        return documents


# ── GitHub Loader ─────────────────────────────────────────────────────────


class GitHubLoader:
    """Load GitHub content (repos, issues, PRs) as documents.

    Requires the ``PyGithub`` package and GITHUB_TOKEN environment variable.

    Usage:
        loader = GitHubLoader(repo="owner/repo")
        docs = loader.load()  # loads README + issues
        docs = loader.load_issues(state="open", limit=10)
    """

    def __init__(self, repo: str, github_token: str | None = None):
        self.repo_full = repo
        self._token = github_token

    def _get_client(self):
        import os
        from github import Github
        return Github(self._token or os.environ.get("GITHUB_TOKEN", ""))

    def load(self, include_readme: bool = True, include_issues: bool = False) -> list[Document]:
        """Load repository content.

        Args:
            include_readme: Include the repository README.
            include_issues: Include open issues.

        Returns:
            List of Document objects.
        """
        g = self._get_client()
        repo = g.get_repo(self.repo_full)
        documents = []

        if include_readme:
            try:
                readme = repo.get_readme()
                import base64
                content = base64.b64decode(readme.content).decode("utf-8")
                documents.append(Document(
                    page_content=content,
                    metadata={"source": f"github://{self.repo_full}/README", "file_type": "github", "repo": self.repo_full},
                ))
            except Exception:
                pass

        if include_issues:
            issues = repo.get_issues(state="open", sort="updated", direction="desc")[:20]
            for issue in issues:
                body = issue.body or ""
                documents.append(Document(
                    page_content=f"Title: {issue.title}\n\n{body}",
                    metadata={
                        "source": f"github://{self.repo_full}/issues/{issue.number}",
                        "file_type": "github",
                        "repo": self.repo_full,
                        "issue_number": issue.number,
                        "state": issue.state,
                    },
                ))

        return documents

    def load_issues(self, state: str = "open", limit: int = 10, label: str | None = None) -> list[Document]:
        """Load GitHub issues as documents.

        Args:
            state: "open", "closed", or "all".
            limit: Maximum number of issues to load.
            label: Filter by label name.

        Returns:
            List of Document objects.
        """
        g = self._get_client()
        repo = g.get_repo(self.repo_full)
        documents = []

        kwargs = {"state": state, "sort": "updated", "direction": "desc"}
        issues = repo.get_issues(**kwargs)[:limit]

        for issue in issues:
            if label and label not in [l.name for l in issue.labels]:
                continue
            body = issue.body or ""
            labels_str = ", ".join(l.name for l in issue.labels) if issue.labels else ""
            content = f"Title: {issue.title}\nLabels: {labels_str}\n\n{body}"
            documents.append(Document(
                page_content=content,
                metadata={
                    "source": f"github://{self.repo_full}/issues/{issue.number}",
                    "file_type": "github_issue",
                    "repo": self.repo_full,
                    "issue_number": issue.number,
                    "state": issue.state,
                    "labels": labels_str,
                },
            ))

        return documents
