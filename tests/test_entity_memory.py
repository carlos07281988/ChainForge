"""Tests for entity memory."""
import pytest
from chainforge.memory.entity import EntityMemory, Entity


class TestEntity:
    def test_creation(self):
        e = Entity(name="Alice", type="person")
        assert e.name == "Alice"
        assert e.mention_count == 0
        assert e.mentions == []


class TestEntityMemory:
    def test_extract_person(self):
        mem = EntityMemory()
        updated = mem.extract("John works at Google.")
        assert "John" in updated
        assert "Google" in updated

    def test_extract_location(self):
        mem = EntityMemory()
        updated = mem.extract("She lives in Paris.")
        assert "Paris" in updated

    def test_mention_count(self):
        mem = EntityMemory()
        mem.extract("Alice is a developer.")
        mem.extract("Alice likes Python.")
        mem.extract("Alice said hello.")
        assert mem.entities["Alice"].mention_count == 3

    def test_get_entities_filtered(self):
        mem = EntityMemory()
        mem.extract("Alice is a person. Google is a company.")
        persons = mem.get_entities(entity_type="person")
        assert "Alice" in persons

    def test_get_context(self):
        mem = EntityMemory()
        mem.extract("Alice works in Beijing.")
        context = mem.get_context()
        assert "Alice" in context
        assert "Beijing" in context

    def test_empty_context(self):
        mem = EntityMemory()
        assert mem.get_context() == ""

    def test_clear(self):
        mem = EntityMemory()
        mem.extract("Alice is here.")
        assert len(mem.entities) > 0
        mem.clear()
        assert len(mem.entities) == 0

    def test_extract_with_source(self):
        mem = EntityMemory()
        updated = mem.extract("Bob said hello.", source="user")
        assert "Bob" in updated
