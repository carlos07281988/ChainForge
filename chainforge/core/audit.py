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
"""Auditable Execution Chain — cryptographically chained agent execution logs.

Each agent event is recorded in an append-only log with SHA-256 hash
chaining. Modifying any entry invalidates all subsequent hashes, providing
tamper-evident audit trails for compliance and debugging.

Usage:
    from chainforge.core.audit import AuditLog, audit_middleware

    log = AuditLog(session_id="session-1")
    agent = Agent(llm=llm, middlewares=[audit_middleware(log)])
    stream = await agent.run("Hello")

    # Verify integrity
    report = log.verify()
    # {"valid": True, "entries": 42, "tampered": []}
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field

from chainforge.core.message import Message
from chainforge.core.stream import EventType, StreamEvent
from chainforge.logging import get_logger

logger = get_logger("core.audit")

_GENESIS_PREV_HASH = "0" * 64


# ── AuditEntry ────────────────────────────────────────────────────────────


class AuditEntry(BaseModel):
    """A single entry in the audit log with hash-chain integrity."""

    index: int = Field(description="Sequence number (0-based)")
    timestamp: float = Field(description="Entry creation time")
    session_id: str = Field(default="", description="Session identifier")
    event_type: str = Field(description="Type of event recorded")
    data_summary: str = Field(default="", description="Short text summary of the event")
    previous_hash: str = Field(description="SHA-256 hex digest of the previous entry")
    hash: str = Field(description="SHA-256 hex digest of this entry")

    def compute_hash(self) -> str:
        """Recompute the expected hash for this entry."""
        content = (
            self.previous_hash
            + str(self.index)
            + str(self.timestamp)
            + self.session_id
            + self.event_type
            + self.data_summary
        )
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def verify_hash(self) -> bool:
        """Check if this entry's hash matches its content."""
        return self.hash == self.compute_hash()

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "event_type": self.event_type,
            "data_summary": self.data_summary[:200],
            "previous_hash": self.previous_hash,
            "hash": self.hash,
        }

    def __repr__(self) -> str:
        return (f"AuditEntry({self.index}: {self.event_type} "
                f"[{self.hash[:12]}...])")


# ── AuditLog ──────────────────────────────────────────────────────────────


class AuditLog(BaseModel):
    """Append-only audit log with SHA-256 hash chaining.

    Each entry is cryptographically linked to the previous one, forming
    a tamper-evident chain. The log can be verified for integrity,
    exported to JSON, and reconstructed from exported data.

    Usage:
        log = AuditLog(session_id="sess-1")
        log.record("user_input", "Hello")
        log.record("tool_call", "search(query=...)")

        report = log.verify()
        assert report["valid"]

        data = log.export()
        restored = AuditLog.from_entries(data)
        assert restored.verify()["valid"]
    """

    session_id: str = Field(default="default", description="Session identifier")
    _entries: list[AuditEntry] = []

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self._entries = []

    # ── Properties ──────────────────────────────────────────────────────

    @property
    def entries(self) -> list[AuditEntry]:
        return list(self._entries)

    @property
    def count(self) -> int:
        return len(self._entries)

    @property
    def last_hash(self) -> str:
        if not self._entries:
            return _GENESIS_PREV_HASH
        return self._entries[-1].hash

    # ── Recording ───────────────────────────────────────────────────────

    def record(self, event_type: str, data: str | dict[str, Any] | None = None,
               session_id: str | None = None) -> AuditEntry:
        """Record a new entry in the audit log.

        Args:
            event_type: Type of event (e.g., "user_input", "tool_call").
            data: Event data — string or dict (converted to summary).
            session_id: Optional override for the session ID.

        Returns:
            The newly created AuditEntry.
        """
        # Summarize data
        if data is None:
            summary = ""
        elif isinstance(data, str):
            summary = data
        elif isinstance(data, dict):
            # Create a compact summary
            parts = []
            for k, v in data.items():
                s = str(v)
                if len(s) > 80:
                    s = s[:77] + "..."
                parts.append(f"{k}={s}")
            summary = ", ".join(parts)
        else:
            summary = str(data)

        entry = AuditEntry(
            index=self.count,
            timestamp=time.time(),
            session_id=session_id or self.session_id,
            event_type=event_type,
            data_summary=summary[:500],
            previous_hash=self.last_hash,
            hash="",  # computed below
        )
        # Compute hash after all fields are set
        entry.hash = entry.compute_hash()
        self._entries.append(entry)
        return entry

    # ── Verification ────────────────────────────────────────────────────

    def verify(self) -> dict[str, Any]:
        """Verify the integrity of the entire hash chain.

        Returns:
            dict with:
              - valid: True if no tampering detected
              - entries: total entry count
              - tampered: list of indices where hash doesn't match
              - chain_broken: list of indices where chain link is broken
        """
        tampered: list[int] = []
        chain_broken: list[int] = []

        for i, entry in enumerate(self._entries):
            # 1. Check that this entry's hash matches its content
            if not entry.verify_hash():
                tampered.append(i)

            # 2. Check that the chain link is valid
            if i > 0:
                expected_prev = self._entries[i - 1].hash
                if entry.previous_hash != expected_prev:
                    chain_broken.append(i)

        return {
            "valid": len(tampered) == 0 and len(chain_broken) == 0,
            "entries": self.count,
            "tampered": tampered,
            "chain_broken": chain_broken,
        }

    def export(self) -> list[dict[str, Any]]:
        """Export all entries as a list of dicts (JSON-serializable)."""
        return [e.to_dict() for e in self._entries]

    def export_json(self, path: str, indent: int = 2) -> None:
        """Export the audit log to a JSON file."""
        data = {
            "session_id": self.session_id,
            "count": self.count,
            "entries": self.export(),
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=indent)

    @classmethod
    def from_entries(cls, entries: list[dict[str, Any]],
                     session_id: str = "restored") -> "AuditLog":
        """Reconstruct an AuditLog from exported data.

        Args:
            entries: List of entry dicts (from export()).
            session_id: Session ID for the restored log.

        Returns:
            AuditLog with the imported entries.
        """
        log = cls(session_id=session_id)
        for e_data in entries:
            entry = AuditEntry(**e_data)
            log._entries.append(entry)
        return log

    @classmethod
    def from_json(cls, path: str) -> "AuditLog":
        """Load an AuditLog from a JSON file."""
        with open(path) as f:
            data = json.load(f)
        return cls.from_entries(
            data.get("entries", []),
            session_id=data.get("session_id", "loaded"),
        )

    def summary(self) -> dict[str, Any]:
        """Get summary statistics about the audit log."""
        type_counts: dict[str, int] = {}
        for e in self._entries:
            type_counts[e.event_type] = type_counts.get(e.event_type, 0) + 1
        return {
            "session_id": self.session_id,
            "entries": self.count,
            "by_type": type_counts,
            "valid": self.verify()["valid"],
        }


# ── Middleware ──────────────────────────────────────────────────────────────


def audit_middleware(log: AuditLog):
    """Create middleware that records agent events to an audit log.

    Usage:
        log = AuditLog(session_id="sess-1")
        agent = Agent(llm=llm, middlewares=[audit_middleware(log)])
    """
    async def _audit_mw(
        messages: list[Message],
        ctx: dict[str, Any],
        next_handler: callable,
    ) -> AsyncIterator[StreamEvent]:
        log.record("agent_run", data=f"{len(messages)} messages")

        async for event in next_handler(messages, ctx):
            if event.type == EventType.text and event.content:
                log.record("text", data=event.content[:200])

            elif event.type == EventType.tool_call:
                log.record("tool_call", data={
                    "name": event.data.get("name", "?"),
                    "args": event.data.get("args", {}),
                })

            elif event.type == EventType.tool_result:
                log.record("tool_result", data={
                    "name": event.data.get("name", "?"),
                    "result": (event.data.get("content", "") or "")[:200],
                    "is_error": event.data.get("is_error", False),
                })

            elif event.type == EventType.error:
                log.record("error", data=event.content or "")

            elif event.type == EventType.state:
                log.record("state", data={
                    "state": event.data.get("state", ""),
                    "iteration": event.data.get("iteration", 0),
                })

            yield event

    return _audit_mw


__all__ = [
    "AuditEntry",
    "AuditLog",
    "audit_middleware",
]
