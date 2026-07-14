# Agent Inspector — Browser-Based Debugger

> 为 ChainForge Agent 提供实时调试和监控面板

## Motivation

Agent 是黑盒——给一个 prompt，得到一个回答，中间发生了什么很难追踪。需要：
1. 实时查看 agent 状态变化
2. 查看 tool call 历史和中间结果
3. 查看记忆内容
4. 分析执行性能（耗时、迭代次数）

## Design

### Data Model

```
AgentInspection
├── agent_id
├── events[]          # InspectionEvent 列表
│   ├── type          # state, text, tool_call, tool_result, error
│   ├── state         # 当前 agent state
│   ├── iteration     # 循环次数
│   ├── content       # 事件内容
│   ├── data          # 元数据
│   └── duration_ms   # 距开始时间
├── tool_call_count
├── error_count
└── total_iterations
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/inspector/agents` | List tracked agents |
| GET | `/api/v1/inspector/agents/{id}` | Agent execution summary |
| GET | `/api/v1/inspector/agents/{id}/events` | Events with filtering |
| GET | `/api/v1/inspector/agents/{id}/events/stream` | SSE live stream |

### Files

| File | Description |
|------|-------------|
| `chainforge/inspector/__init__.py` | Exports |
| `chainforge/inspector/inspector.py` | AgentInspector, InspectionEvent |
| `chainforge/inspector/api.py` | FastAPI router |
| `tests/test_inspector.py` | Tests |
