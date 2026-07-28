"""ChainForge Enterprise: Agent Fine-Tuning Loop example.

Usage:
    python examples/enterprise/finetune_example.py
"""
import asyncio, sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from chainforge.enterprise.finetune import (
    FineTuningLoop, TrainingDataCleaner, QualityGate, LoRATrainer,
)
from chainforge.enterprise.collective import CollectiveMemory, Experience
from chainforge.enterprise.distill.adapter import LoRAConfig

async def main():
    print("=== Agent Fine-Tuning Loop ===\n")

    # 1. Training Data Cleaner -- filter raw experience dicts
    now = time.time()
    cleaner = TrainingDataCleaner()
    raw_experiences = [
        {"id": "e1", "task": "refund order", "outcome": "success", "cost": 0.05, "timestamp": now - 86400},
        {"id": "e2", "task": "refund partial", "outcome": "success", "cost": 0.03, "timestamp": now - 43200},
        {"id": "e3", "task": "refund failed", "outcome": "failure", "cost": 0.08, "timestamp": now - 3600},
        {"id": "e4", "task": "refund fast", "outcome": "success", "cost": 0.02, "timestamp": now - 1000},
        {"id": "e5", "task": "ancient refund", "outcome": "success", "cost": 0.04, "timestamp": now - 86400 * 100},
        {"id": "e6", "task": "account query", "outcome": "success", "cost": 0.01, "timestamp": now},
    ]
    cleaned = cleaner.clean(raw_experiences, min_success_rate=0.8, max_age_days=90)
    print("1. Training Data Cleaner:")
    print(f"   Input: {len(raw_experiences)} experiences")
    print(f"   Keep: {len(cleaned)} clean pairs")
    print("   Removed: 1 failure (e3), 1 ancient (e5)")

    # 2. Quality Gate -- validate Experience objects
    gate = QualityGate(min_experiences=3, min_success_rate=0.8, max_age_days=90)
    experiences = [
        Experience(id=e["id"], task=e["task"], task_type="refund" if "refund" in e.get("task", "") else "account",
                   outcome=e["outcome"], cost=e.get("cost", 0.0), tokens=300,
                   duration_ms=500, timestamp=e["timestamp"])
        for e in raw_experiences
    ]
    report = gate.validate(experiences, filtered_count=len(cleaned))
    print("\n2. Quality Gate:")
    print(f"   Passed: {report.passed}")
    print(f"   Reason: {report.reason}")
    print(f"   Filtered count: {report.filtered_count}/{report.total_count}")

    # 3. LoRA Trainer config
    trainer = LoRATrainer(
        adapter_config=LoRAConfig(r=16, alpha=32),
        base_model="qwen2.5-3b",
    )
    result = trainer.train(dataset=cleaned, framework="unsloth")
    print("\n3. LoRA Trainer:")
    print(f"   Output: {result.output_path}")
    print(f"   Loss: {result.loss:.4f}")
    print(f"   Duration: {result.duration_s:.0f}s")
    print(f"   VRAM used: {result.vram_used_gb} GB")
    print(f"   Framework: {result.framework}")

    # 4. Fine-Tuning Loop -- full pipeline
    cm = CollectiveMemory(namespace="customer-support")
    for e in raw_experiences:
        cm.add(Experience(
            id=e["id"], task=e["task"],
            task_type="refund" if "refund" in e.get("task", "") else "account",
            outcome=e["outcome"], cost=e.get("cost", 0.0),
            tokens=300, duration_ms=500, timestamp=e["timestamp"],
        ))

    loop = FineTuningLoop(
        source_memory=cm,
        target_model="qwen2.5-3b",
        quality_gate=gate,
        min_success_rate=0.8,
        max_age_days=90,
    )
    ft_result = await loop.run()
    print("\n4. Fine-Tuning Loop Result:")
    print(f"   Status: {ft_result.status}")
    print(f"   Training pairs: {ft_result.training_pairs}")
    print(f"   Improvement: {ft_result.improvement_estimate:.0%}")
    print(f"   Eval score: {ft_result.eval_score:.3f}")
    print(f"   Model: {ft_result.model_path}")

if __name__ == "__main__":
    asyncio.run(main())
