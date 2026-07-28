"""ChainForge Enterprise: Durable Agent Execution example.

Usage:
    python examples/enterprise/durable_example.py
"""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from chainforge.enterprise.durable import (
    DurableExecutor, JobHandle, Checkpoint, DeadLetterQueue,
    ExecutionJournal, CrashRecoveryPolicy,
)

async def main():
    print("=== Durable Agent Execution ===\n")

    # 1. DurableExecutor — persistent job execution
    executor = DurableExecutor(
        backend="sqlite",
        checkpoint_every=30,
        crash_recovery=CrashRecoveryPolicy(auto_retry=True, max_retries=3),
    )
    print(f"1. DurableExecutor: backend=sqlite, checkpoint_every=30s")
    print(f"   Crash recovery: auto_retry={executor._crash_recovery.auto_retry}, max_retries={executor._crash_recovery.max_retries}")

    # 2. Submit async jobs
    job = await executor.submit(agent=None, prompt="审计所有 AWS S3 bucket 权限")
    print(f"\n2. Job Submitted:")
    print(f"   Job ID: {job.job_id}")
    print(f"   Status: {job.status}")

    # 3. Checkpoint — save execution state
    cp = Checkpoint(
        job_id=job.job_id, step_index=5, total_steps=20,
        messages_json='[{"role":"user","content":"audit request"}]',
        tokens_used=2500, cost_accumulated=0.05,
        state_snapshot={"current_node": "check_bucket_permissions"},
    )
    print(f"\n3. Checkpoint at step {cp.step_index}/{cp.total_steps}:")
    print(f"   Tokens used: {cp.tokens_used}")
    print(f"   Cost: ${cp.cost_accumulated:.4f}")

    # 4. Dead Letter Queue — failed jobs
    dlq = DeadLetterQueue()
    dlq.enqueue("job-failed-01", step_index=7, reason="tool timeout", agent_id="agent-a")
    dlq.enqueue("job-failed-02", step_index=12, reason="max retries exceeded", agent_id="agent-b")
    print(f"\n4. Dead Letter Queue:")
    print(f"   Items: {dlq.count}")
    for item in dlq.list():
        print(f"   - {item.job_id}: {item.failed_reason} (step {item.step_index})")

    dlq.retry("job-failed-01")
    print(f"   After retry job-failed-01: {dlq.count} remaining")

    # 5. Execution Journal
    journal = ExecutionJournal()
    journal.record("job-abc", 0, "started", detail="Agent run initiated")
    journal.record("job-abc", 1, "llm_call", cost=0.01, tokens=500)
    journal.record("job-abc", 2, "tool_call", detail="query_db")
    journal.record("job-abc", 3, "checkpoint", cost=0.02, tokens=1000)
    journal.record("job-abc", 4, "completed", detail="All checks passed")

    print(f"\n5. Execution Journal (job-abc):")
    trace = journal.trace("job-abc")
    for step in trace:
        icon = {"started":"▶️","llm_call":"🧠","tool_call":"🔧","checkpoint":"💾","completed":"✅"}.get(step.event_type, "❓")
        print(f"   {icon} Step {step.step_index}: {step.event_type} — {step.detail}")

    summary = journal.summary("job-abc")
    print(f"\n   Summary: {summary['total_steps']} steps, ${summary['total_cost']:.4f}, {summary['total_tokens']} tokens")

    # 6. Stats
    stats = executor.stats()
    print(f"\n6. Executor Stats: {stats['total_jobs']} jobs, {stats['dlq_items']} DLQ items")

if __name__ == "__main__":
    asyncio.run(main())
