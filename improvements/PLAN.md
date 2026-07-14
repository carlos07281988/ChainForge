See [ROADMAP.md](./ROADMAP.md) for the full feature roadmap and strategic priorities.

# Phase 2 Feature Plans

Three design documents for the next implementation phase:

| Priority | Feature | Design Doc | Status |
|----------|---------|------------|--------|
| P0 | Code Sandbox + Multi-modal | [`SANDBOX.md`](./SANDBOX.md) | 🛠 Implementing |
| P0 | Memory 2.0 (Vector Memory) | [`MEMORY.md`](./MEMORY.md) | 🛠 Implementing |
| P0 | Agent Config Declaration | [`AGENT_CONFIG.md`](./AGENT_CONFIG.md) | 🛠 Implementing |

---

# Bug Fixes — ChainForge v0.1.0

## Priority: 🔴 Critical (Fix Now)

| # | Issue | File | Risk |
|---|-------|------|------|
| 1 | `eval()` in `calculate` builtin tool — security risk | `chainforge/tools/builtin.py:21` | Security |
| 2 | Bedrock streaming tool call input accumulation not implemented | `chainforge/providers/bedrock.py:200-202` | Bug — data loss |
| 3 | `SummaryMemory` never calls summarize — misnamed | `chainforge/memory/summary.py` | Design/UX |

## Priority: 🟡 High (Fix Before Release)

| # | Issue | File |
|---|-------|------|
| 4 | `PlanAndExecute` JSON parsing is fragile regex-based | `chainforge/agents/plan_execute.py:72-78` |
| 5 | `SelfAsk` sub-question parsing uses same fragile regex | `chainforge/agents/self_ask.py:52-63` |
| 6 | `Agent.skills` type is `list[Any]` — should be `list[Skill]` | `chainforge/core/agent.py:44` |
| 7 | `Agent._execute_tool` assumes `**tc.args` is dict — may crash on string args | `chainforge/core/agent.py:99` |
| 8 | `ConversationalAgent.__init__` uses custom `__init__` instead of `model_post_init` | `chainforge/agents/conversational.py:55` |

## Priority: 🔵 Medium (Improve)

| # | Issue | File |
|---|-------|------|
| 9 | `RateLimitMiddleware` uses `nonlocal` closure state — shared state semantics unclear | `chainforge/middleware/rate_limit.py:39` |
| 10 | `HumanInTheLoop.middleware()` intercepts tool_call events — fragile ordering | `chainforge/core/human_in_loop.py:104` |
| 11 | `GoogleProvider._get_client()` uses global `genai.configure()` — not thread-safe | `chainforge/providers/google.py:41` |
| 12 | Scattered `import asyncio` in function bodies — inconsistent style | Multiple files |
