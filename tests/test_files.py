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
"""Tests for the file handling module."""

import json
import os
import tempfile
from pathlib import Path

from chainforge.core.files import FileLoader, FileContent, load_file, load_image


class TestFileLoader:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def _write(self, name: str, content: str | bytes) -> str:
        path = Path(self.tmpdir) / name
        if isinstance(content, str):
            path.write_text(content)
        else:
            path.write_bytes(content)
        return str(path)

    def test_load_text_file(self):
        path = self._write("test.txt", "Hello, world!")
        loader = FileLoader()
        fc = loader.load(path)
        assert fc.filename == "test.txt"
        assert fc.text == "Hello, world!"
        assert fc.is_image is False

    def test_load_python_file(self):
        path = self._write("script.py", "def foo(): pass")
        fc = load_file(path)
        assert fc.filename == "script.py"
        assert "def foo" in fc.text

    def test_load_json(self):
        data = {"key": "value", "num": 42}
        path = self._write("data.json", json.dumps(data))
        loader = FileLoader()
        loaded = loader.load_json(path)
        assert loaded == data

    def test_load_csv(self):
        csv_content = "name,age\nAlice,30\nBob,25"
        path = self._write("data.csv", csv_content)
        loader = FileLoader()
        rows = loader.load_csv(path)
        assert len(rows) == 2
        assert rows[0]["name"] == "Alice"
        assert rows[1]["age"] == "25"

    def test_detect_image(self):
        loader = FileLoader()
        assert loader.detect("photo.png") == "image"
        assert loader.detect("photo.jpg") == "image"
        assert loader.detect("photo.jpeg") == "image"
        assert loader.detect("photo.gif") == "image"

    def test_detect_text(self):
        loader = FileLoader()
        assert loader.detect("readme.md") == "text"
        assert loader.detect("script.py") == "text"
        assert loader.detect("page.html") == "text"

    def test_detect_data(self):
        loader = FileLoader()
        assert loader.detect("data.json") == "data"
        assert loader.detect("data.csv") == "data"

    def test_load_nonexistent(self):
        loader = FileLoader()
        try:
            loader.load("/nonexistent/file.txt")
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError:
            pass


class TestFileContent:
    def test_repr(self):
        fc = FileContent(data=b"hello", mime_type="text/plain", filename="test.txt")
        r = repr(fc)
        assert "test.txt" in r
        assert "text/plain" in r

    def test_base64(self):
        fc = FileContent(data=b"hello", mime_type="text/plain")
        import base64
        assert fc.base64 == base64.b64encode(b"hello").decode()

    def test_is_image(self):
        img = FileContent(data=b"", mime_type="image/png")
        assert img.is_image is True
        txt = FileContent(data=b"", mime_type="text/plain")
        assert txt.is_image is False
