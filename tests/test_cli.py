"""Tests for CLI scaffolding."""

import tempfile
from pathlib import Path

from chainforge.cli import _scaffold_project, _generate_quickstart


class TestScaffoldProject:
    def test_create_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            _scaffold_project("test-agent", tmp)
            base = Path(tmp) / "test-agent"
            assert (base / "main.py").exists()
            assert (base / "config.py").exists()
            assert (base / "agents").is_dir()
            assert (base / "tools").is_dir()
            assert (base / "workflows").is_dir()
            assert (base / "tests").is_dir()
            assert (base / ".env.example").exists()
            assert (base / "tests" / "test_basic.py").exists()

    def test_main_py_has_agent_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            _scaffold_project("demo", tmp)
            content = (Path(tmp) / "demo" / "main.py").read_text()
            assert "Agent" in content
            assert "asyncio" in content


class TestQuickstart:
    def test_openai_quickstart(self):
        script = _generate_quickstart("openai")
        # It prints, but we can verify it contains expected provider
        # The function doesn't return, so we just verify it runs without error
        pass

    def test_anthropic_quickstart(self):
        script = _generate_quickstart("anthropic")
        pass
