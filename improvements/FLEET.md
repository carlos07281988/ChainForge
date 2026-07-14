# Fleet Management — Worker Pool & Task Queue

> 为 ChainForge Agent 提供并发执行和任务调度能力

## Motivation

单个 agent 实例处理任务有瓶颈：
1. 多个用户/任务需要并发处理
2. 高优先级任务需要插队
3. 需要监控 worker 状态和性能

## Design

### Architecture

```
TaskQueue (priority heap)
    ↓
WorkerPool
    ├── Worker(agent-A)
    ├── Worker(agent-B)
    └── Worker(agent-C)
```

### Components

| Component | Description |
|-----------|-------------|
| `Worker` | 包装一个 agent 实例，管理并发执行 |
| `WorkerPool` | 管理 worker 注册、分发任务 |
| `TaskQueue` | 优先级堆队列，支持 critical/high/normal/low |
| `Task` | 任务单元，含优先级、agent_id、prompt |

### Usage

```python
from chainforge.fleet import WorkerPool, TaskQueue, TaskPriority

pool = WorkerPool(workers=4)
pool.register("assistant", my_agent)

# Single execution
result = await pool.run("assistant", "What is the weather?")

# Parallel execution
results = await pool.run_all("Analyze this data")
# {"agent-A": "result A", "agent-B": "result B"}

# With queue
queue = TaskQueue()
queue.put("assistant", "High priority task", priority=TaskPriority.high)
task = await queue.get()
result = await pool.run(task.agent_id, task.prompt)
queue.complete(task, result=result)
```

### Files

| File | Description |
|------|-------------|
| `chainforge/fleet/__init__.py` | Exports |
| `chainforge/fleet/worker.py` | Worker, WorkerPool |
| `chainforge/fleet/queue.py` | Task, TaskQueue, TaskPriority |
| `tests/test_fleet.py` | Tests |
