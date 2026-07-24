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
"""Tests for Auditable Execution Chain."""

import json
import os
import tempfile

import pytest

from chainforge.core.audit import AuditEntry, AuditLog, audit_middleware


# ── Test AuditEntry ────────────────────────────────────────────────────────


class TestAuditEntry:
    def test_create_entry(self):
        entry = AuditEntry(
            index=0, timestamp=1000.0, event_type="test",
            previous_hash="0" * 64, hash="",
        )
        assert entry.index == 0
        assert entry.event_type == "test"

    def test_compute_hash(self):
        entry = AuditEntry(
            index=0, timestamp=1000.0, event_type="test",
            previous_hash="0" * 64, hash="",
        )
        h = entry.compute_hash()
        assert len(h) == 64  # SHA-256 hex
        assert all(c in "0123456789abcdef" for c in h)

    def test_verify_hash(self):
        entry = AuditEntry(
            index=0, timestamp=1000.0, event_type="test",
            previous_hash="0" * 64, hash="",
        )
        entry.hash = entry.compute_hash()
        assert entry.verify_hash()

    def test_verify_hash_fail(self):
        entry = AuditEntry(
            index=0, timestamp=1000.0, event_type="test",
            previous_hash="0" * 64, hash="x" * 64,
        )
        assert not entry.verify_hash()

    def test_deterministic_hash(self):
        e1 = AuditEntry(
            index=0, timestamp=1000.0, event_type="a",
            previous_hash="0" * 64, hash="",
        )
        e2 = AuditEntry(
            index=0, timestamp=1000.0, event_type="a",
            previous_hash="0" * 64, hash="",
        )
        assert e1.compute_hash() == e2.compute_hash()

    def test_repr(self):
        entry = AuditEntry(
            index=5, timestamp=1000.0, event_type="tool_call",
            previous_hash="0" * 64, hash="",
        )
        r = repr(entry)
        assert "5" in r
        assert "tool_call" in r

    def test_to_dict(self):
        entry = AuditEntry(
            index=0, timestamp=1000.0, event_type="test",
            previous_hash="0" * 64, hash="abcd" * 16,
        )
        d = entry.to_dict()
        assert d["index"] == 0
        assert d["event_type"] == "test"
        assert d["hash"] == "abcd" * 16


# ── Test AuditLog ──────────────────────────────────────────────────────────


class TestAuditLog:
    def test_create(self):
        log = AuditLog(session_id="test")
        assert log.count == 0
        assert log.session_id == "test"

    def test_record(self):
        log = AuditLog()
        entry = log.record("test_event", data="hello")
        assert log.count == 1
        assert entry.index == 0
        assert entry.event_type == "test_event"

    def test_record_sequential_indices(self):
        log = AuditLog()
        for i in range(5):
            log.record("event", data=str(i))
        assert log.count == 5
        for i, e in enumerate(log.entries):
            assert e.index == i

    def test_record_string_data(self):
        log = AuditLog()
        log.record("test", data="simple string")
        assert log.entries[0].data_summary == "simple string"

    def test_record_dict_data(self):
        log = AuditLog()
        log.record("tool_call", data={"name": "search", "args": {"q": "test"}})
        summary = log.entries[0].data_summary
        assert "search" in summary
        assert "test" in summary

    def test_record_none_data(self):
        log = AuditLog()
        log.record("state")
        assert log.entries[0].data_summary == ""

    def test_hash_chain(self):
        log = AuditLog()
        e0 = log.record("first")
        e1 = log.record("second")
        assert e0.previous_hash == "0" * 64
        assert e1.previous_hash == e0.hash

    def test_last_hash(self):
        log = AuditLog()
        assert log.last_hash == "0" * 64
        e = log.record("test")
        assert log.last_hash == e.hash

    def test_verify_empty(self):
        log = AuditLog()
        report = log.verify()
        assert report["valid"]
        assert report["entries"] == 0

    def test_verify_valid(self):
        log = AuditLog()
        log.record("a")
        log.record("b")
        log.record("c")
        report = log.verify()
        assert report["valid"]
        assert report["entries"] == 3
        assert report["tampered"] == []
        assert report["chain_broken"] == []

    def test_verify_tampered_content(self):
        log = AuditLog()
        log.record("a")
        log.record("b")
        log._entries[0].data_summary = "MODIFIED"
        report = log.verify()
        assert not report["valid"]
        assert 0 in report["tampered"]

    def test_verify_broken_chain(self):
        log = AuditLog()
        log.record("a")
        log.record("b")
        log._entries[1].previous_hash = "x" * 64
        report = log.verify()
        assert not report["valid"]
        assert 1 in report["chain_broken"]

    def test_export(self):
        log = AuditLog()
        log.record("a", data="hello")
        log.record("b", data="world")
        data = log.export()
        assert len(data) == 2
        assert data[0]["event_type"] == "a"
        assert data[1]["event_type"] == "b"
        # Hashes should be included
        assert len(data[0]["hash"]) == 64

    def test_from_entries(self):
        log = AuditLog()
        log.record("a")
        log.record("b")
        data = log.export()
        restored = AuditLog.from_entries(data)
        assert restored.count == 2
        assert restored.verify()["valid"]

    def test_from_entries_different_session(self):
        log = AuditLog(session_id="original")
        log.record("test")
        data = log.export()
        restored = AuditLog.from_entries(data, session_id="restored")
        assert restored.session_id == "restored"

    def test_json_roundtrip(self):
        log = AuditLog(session_id="json-test")
        log.record("event1", data="first")
        log.record("event2", data="second")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            log.export_json(f.name)
            fname = f.name

        loaded = AuditLog.from_json(fname)
        assert loaded.count == 2
        assert loaded.verify()["valid"]
        assert loaded.entries[0].event_type == "event1"
        os.unlink(fname)

    def test_summary(self):
        log = AuditLog()
        log.record("tool_call")
        log.record("tool_result")
        log.record("text")
        s = log.summary()
        assert s["entries"] == 3
        assert s["by_type"]["tool_call"] == 1
        assert s["valid"] is True

    def test_summary_empty(self):
        log = AuditLog()
        s = log.summary()
        assert s["entries"] == 0
        assert s["valid"] is True


# ── Test audit_middleware ──────────────────────────────────────────────────


class TestAuditMiddleware:
    def test_middleware_is_callable(self):
        log = AuditLog()
        mw = audit_middleware(log)
        assert callable(mw)

    def test_middleware_records_events(self):
        from chainforge.core.stream import EventType, Stream, StreamEvent
        from collections.abc import AsyncIterator
        from typing import Any

        log = AuditLog(session_id="mw-test")

        async def handler(msgs, ctx) -> AsyncIterator[StreamEvent]:
            yield StreamEvent(type=EventType.tool_call, data={"name": "search", "args": {"q": "test"}})
            yield StreamEvent(type=EventType.tool_result, data={"name": "search", "content": "results"})
            yield StreamEvent(type=EventType.text, content="Hello there")
            yield StreamEvent(type=EventType.done)

        import asyncio
        mw = audit_middleware(log)
        events = []

        async def run():
            async for e in mw([], {}, handler):
                events.append(e)

        asyncio.run(run())
        assert log.count >= 3  # tool_call, tool_result, text + agent_run
        assert any(e.event_type == "tool_call" for e in log.entries)
        assert any(e.event_type == "tool_result" for e in log.entries)
        assert any(e.event_type == "text" for e in log.entries)
