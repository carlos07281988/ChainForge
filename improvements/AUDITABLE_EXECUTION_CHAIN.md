# Auditable Execution Chain

> Phase 24: Cryptographically signed agent execution logs for compliance and debugging.
> Status: 🛠 Implementing | Priority: P2 | Effort: 10-14 days

---

## Design

Each agent execution event is recorded in an append-only log with SHA-256
hash chaining. Modifying any entry invalidates all subsequent hashes.

```
Entry 0 (Genesis):
  index=0, event_type="user_input", data="Hello",
  previous_hash="0"*64,
  hash=SHA256(previous_hash + "0" + timestamp + "user_input" + "Hello")

Entry 1:
  index=1, event_type="llm_call", data="gpt-4o",
  previous_hash=hash_of_entry_0,
  hash=SHA256(previous_hash + "1" + timestamp + "llm_call" + "gpt-4o")
  ...
```

## API

```python
from chainforge.core.audit import AuditLog, audit_middleware

log = AuditLog(session_id="sess-1")

# Middleware records all agent events automatically
agent = Agent(
    llm=llm,
    middlewares=[audit_middleware(log)],
)
stream = await agent.run("Hello")

# Verify integrity
report = log.verify()
# {"valid": True, entries: 42, "tampered": []}

# Manual recording
log.record("user_input", data="Hello")
log.record("tool_call", data={"name": "search"})

# Export
entries = log.export()
```

## Storage

The log can be persisted to JSON or SQLite. The hash chain means
you can verify integrity even after serialization/deserialization.
