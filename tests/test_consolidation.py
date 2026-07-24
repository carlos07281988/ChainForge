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
"""Tests for Agent Memory Consolidation."""

import pytest

from chainforge.core.consolidation import MemoryConsolidator, ConsolidationConfig


# ── Test ConsolidationConfig ────────────────────────────────────────────────


class TestConsolidationConfig:
    def test_default_config(self):
        cfg = ConsolidationConfig()
        assert cfg.confidence_threshold == 0.3
        assert cfg.max_memories == 500
        assert cfg.enable_compression is True
        assert cfg.llm_assisted is False

    def test_custom_config(self):
        cfg = ConsolidationConfig(
            confidence_threshold=0.5,
            max_memories=100,
            enable_compression=False,
        )
        assert cfg.confidence_threshold == 0.5
        assert cfg.max_memories == 100
        assert cfg.enable_compression is False

    def test_config_ranges(self):
        ConsolidationConfig(confidence_threshold=0.0, recency_weight=0.0)
        ConsolidationConfig(confidence_threshold=1.0, recency_weight=1.0)
        ConsolidationConfig(confidence_threshold=0.5, recency_weight=0.5)


# ── Test MemoryConsolidator ─────────────────────────────────────────────────


class TestMemoryConsolidator:
    def test_create(self):
        c = MemoryConsolidator()
        assert c.config is not None
        assert c.config.confidence_threshold == 0.3

    def test_create_with_config(self):
        cfg = ConsolidationConfig(confidence_threshold=0.7)
        c = MemoryConsolidator(config=cfg)
        assert c.config.confidence_threshold == 0.7

    def test_config_property(self):
        c = MemoryConsolidator()
        assert c.config.confidence_threshold == 0.3


class TestScoreQuality:
    def test_empty_memory(self):
        c = MemoryConsolidator()
        assert c._score_quality("") == 0.0
        assert c._score_quality("   ") == 0.0

    def test_short_memory(self):
        c = MemoryConsolidator()
        score = c._score_quality("Hello world")
        assert 0.3 <= score <= 0.5

    def test_long_memory(self):
        c = MemoryConsolidator()
        score = c._score_quality(" ".join(["word"] * 30))
        assert score > 0.3

    def test_memory_with_numbers(self):
        c = MemoryConsolidator()
        score = c._score_quality("User is 25 years old and has 3 pets")
        assert score >= 0.4  # Base + numbers bonus

    def test_memory_with_proper_nouns(self):
        c = MemoryConsolidator()
        score = c._score_quality("Alice works at Google and lives in New York")
        assert score >= 0.4

    def test_memory_with_quotes(self):
        c = MemoryConsolidator()
        score = c._score_quality('User said "I love Python"')
        assert score > 0.3


class TestReview:
    def test_review_empty(self):
        c = MemoryConsolidator()
        scores = c.review([])
        assert scores == {}

    def test_review_single(self):
        c = MemoryConsolidator()
        scores = c.review(["User likes Python"])
        assert len(scores) == 1
        assert 0.0 <= scores[0] <= 1.0

    def test_review_multiple(self):
        c = MemoryConsolidator()
        memories = ["User likes Python", "User works at Google", "User is 30"]
        scores = c.review(memories)
        assert len(scores) == 3
        for v in scores.values():
            assert 0.0 <= v <= 1.0


class TestPrune:
    def test_prune_below_threshold(self):
        c = MemoryConsolidator()
        memories = ["Low quality", "Higher quality memory with details"]
        scores = {0: 0.1, 1: 0.8}
        kept, pruned = c.prune(memories, scores=scores, threshold=0.3)
        assert len(kept) == 1
        assert len(pruned) == 1
        assert pruned[0] == 0
        assert kept[0] == "Higher quality memory with details"

    def test_prune_all_above(self):
        c = MemoryConsolidator()
        memories = ["Good one", "Also good"]
        scores = {0: 0.7, 1: 0.8}
        kept, pruned = c.prune(memories, scores=scores, threshold=0.3)
        assert len(kept) == 2
        assert len(pruned) == 0

    def test_prune_all_below(self):
        c = MemoryConsolidator()
        memories = ["a", "b"]
        scores = {0: 0.1, 1: 0.1}
        kept, pruned = c.prune(memories, scores=scores, threshold=0.5)
        assert len(kept) == 0
        assert len(pruned) == 2

    def test_prune_default_threshold(self):
        c = MemoryConsolidator(config=ConsolidationConfig(confidence_threshold=0.5))
        memories = ["Low", "Higher quality memory with details more info longer"]
        kept, pruned = c.prune(memories)
        assert len(kept) >= 0
        assert len(pruned) >= 0
        assert len(kept) + len(pruned) == 2

    def test_prune_empty(self):
        c = MemoryConsolidator()
        kept, pruned = c.prune([])
        assert kept == []
        assert pruned == []


class TestFindRelated:
    def test_related_by_keyword(self):
        c = MemoryConsolidator()
        memories = [
            "User likes Python programming",
            "User writes Python code daily",
            "User enjoys hiking in mountains",
        ]
        groups = c._find_related(memories)
        assert len(groups) >= 1
        # First two should be related (Python)
        related_group = [g for g in groups if 0 in g and 1 in g]
        assert len(related_group) >= 1

    def test_no_related(self):
        c = MemoryConsolidator()
        memories = [
            "Python programming",
            "Mountain hiking",
            "Cooking recipes",
        ]
        groups = c._find_related(memories)
        # Unlikely to find many relations between disparate topics
        assert isinstance(groups, list)


class TestCompress:
    def test_compress_disabled(self):
        cfg = ConsolidationConfig(enable_compression=False)
        c = MemoryConsolidator(config=cfg)
        memories = ["A", "B", "C"]
        result, events = c.compress(memories)
        assert result == memories
        assert events == []

    def test_compress_related(self):
        c = MemoryConsolidator()
        memories = [
            "User likes Python programming",
            "User writes Python code",
        ]
        result, events = c.compress(memories)
        # Related memories should be merged
        assert len(result) <= len(memories)


class TestConsolidate:
    def test_consolidate_empty(self):
        c = MemoryConsolidator()
        report = c.consolidate([])
        assert report["reviewed"] == 0
        assert report["remaining"] == 0

    def test_consolidate_all_high_quality(self):
        c = MemoryConsolidator()
        memories = [
            "User is a software engineer with 10 years of experience",
            "User works at Google in the AI division",
            "User prefers Python and TypeScript for development",
        ]
        report = c.consolidate(memories)
        assert report["reviewed"] == 3
        assert report["remaining"] >= 1
        assert report["retention_rate"] > 0

    def test_consolidate_mixed(self):
        c = MemoryConsolidator(config=ConsolidationConfig(confidence_threshold=0.5))
        memories = [
            "High quality detailed memory with many specifics and details",
            "Short",
            "Another detailed memory about Python development skills",
        ]
        report = c.consolidate(memories)
        assert report["reviewed"] == 3
        assert report["remaining"] >= 1  # At least the good ones survive

    def test_pattern_extraction(self):
        c = MemoryConsolidator()
        memories = [
            "User likes Python",
            "User likes Python for data science",
            "User enjoys hiking",
        ]
        patterns = c._extract_patterns(memories, {})
        assert len(patterns) > 0
        # "python" should be a top keyword
        python_patterns = [p for p in patterns if p["keyword"] == "python"]
        assert len(python_patterns) >= 1

    def test_consolidate_report_structure(self):
        c = MemoryConsolidator()
        memories = ["User likes Python", "User works at Google"]
        report = c.consolidate(memories)
        for key in ["reviewed", "pruned", "compressed", "remaining",
                     "retention_rate", "patterns", "avg_confidence"]:
            assert key in report, f"Missing key: {key}"


class TestAccessTracking:
    def test_record_access(self):
        c = MemoryConsolidator()
        c.record_access(0)
        assert c._access_counts[0] == 1
        c.record_access(0)
        assert c._access_counts[0] == 2

    def test_record_creation(self):
        c = MemoryConsolidator()
        c.record_creation(0)
        assert 0 in c._creation_times
        assert c._creation_times[0] > 0


class TestExtractPatterns:
    def test_empty_memories(self):
        c = MemoryConsolidator()
        assert c._extract_patterns([], {}) == []

    def test_pattern_discovery(self):
        c = MemoryConsolidator()
        memories = [
            "User likes Python for web development",
            "User uses Python for data analysis",
            "User prefers Python over other languages",
            "User enjoys mountain biking",
        ]
        patterns = c._extract_patterns(memories, {})
        keywords = [p["keyword"] for p in patterns]
        assert "python" in keywords
